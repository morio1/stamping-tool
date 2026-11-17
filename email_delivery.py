"""Reviewed Gmail delivery: one recipient, one verified output PDF per message."""
import csv
import hashlib
import json
import os
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path, PurePosixPath

from stamper import digest


@dataclass(frozen=True)
class Delivery:
    email: str
    recipient_name: str
    certificate: str
    path: Path
    sha256: str


def validate_email(value):
    value = value.strip()
    if any(c.isspace() for c in value) or any(c in value for c in ',;<>'):
        raise ValueError("Use exactly one plain email address per row")
    try:
        address = Address(addr_spec=value)
    except Exception:
        raise ValueError("Invalid email address") from None
    if not address.username or not address.domain or "." not in address.domain:
        raise ValueError("Invalid email address")
    return value


def load_plan(csv_path, output, audit, progress=None, cancelled=None):
    output = Path(output).resolve()
    rows = json.loads(Path(audit).read_text(encoding="utf-8"))
    successful = {r["file"].replace("\\", "/"): r for r in rows if r.get("status") in ("stamped", "signed")}
    plan, seen = [], set()
    with open(csv_path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not {"email", "certificate"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV requires email and certificate columns; recipient_name is optional")
        for number, row in enumerate(reader, 2):
            if cancelled and cancelled():
                raise ValueError("Recipient validation cancelled")
            email = validate_email(row["email"] or "")
            relative = str(PurePosixPath((row["certificate"] or "").strip().replace("\\", "/")))
            path = (output / relative).resolve()
            record = successful.get(relative)
            if not record or not path.is_relative_to(output) or path.suffix.lower() != ".pdf" or not path.is_file():
                raise ValueError(f"Row {number}: PDF is not a successful output in the selected audit")
            if path.stat().st_size > 18 * 1024**2:
                raise ValueError(f"Row {number}: PDF exceeds the 18 MiB attachment limit")
            sha = digest(path)
            if sha != record.get("output_sha256"):
                raise ValueError(f"Row {number}: certificate changed since export")
            key = (email.casefold(), relative.casefold())
            if key in seen:
                raise ValueError(f"Row {number}: duplicate recipient/certificate mapping")
            seen.add(key)
            plan.append(Delivery(email, row.get("recipient_name", "") or "Recipient", relative, path, sha))
            if progress:
                progress(len(plan))
    if not plan:
        raise ValueError("Recipient CSV has no rows")
    return plan


def make_message(item, sender, subject, body):
    sender = validate_email(sender)
    values = {"name": item.recipient_name, "certificate": Path(item.certificate).name}
    subject, body = subject.format_map(values), body.format_map(values)
    if not subject.strip() or "\n" in subject or "\r" in subject:
        raise ValueError("Subject must be a single non-empty line")
    content = item.path.read_bytes()
    if hashlib.sha256(content).hexdigest() != item.sha256:
        raise ValueError("Certificate changed since recipient review; reload the plan")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, item.email, subject
    message["Message-ID"] = make_msgid(domain=sender.split("@", 1)[1])
    message.set_content(body)
    message.add_attachment(content, maintype="application", subtype="pdf", filename=Path(item.certificate).name)
    return message


def delivery_key(item, sender):
    return hashlib.sha256(f"{sender.casefold()}|{item.email.casefold()}|{item.sha256}".encode()).hexdigest()


def send_batch(plan, sender, password, subject, body, output, *, reviewed=False, limit=100,
               pause_seconds=2, cancelled=None, progress=None, smtp_factory=smtplib.SMTP_SSL):
    if not reviewed:
        raise ValueError("Review the recipient/attachment mapping before sending")
    sender = validate_email(sender)
    if not 1 <= limit <= 1000 or pause_seconds < 0:
        raise ValueError("Batch limit must be 1-1000 and pause must be nonnegative")
    output = Path(output).resolve()
    journal = output / "email-delivery.jsonl"
    lock = output / ".email-send.lock"
    # One sending process per output folder. A crash leaves a lock for deliberate review.
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    results = []
    try:
        previous = {}
        if journal.exists():
            for line in journal.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                previous[entry["key"]] = entry["status"]
        def log(item, key, status):
            entry = {"time": datetime.now(timezone.utc).isoformat(), "key": key,
                     "sender": sender,
                     "email": item.email, "certificate": item.certificate, "sha256": item.sha256, "status": status}
            with journal.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            previous[key] = status
            return entry
        # Validate the whole plan and templates before establishing a connection.
        for item in plan:
            make_message(item, sender, subject, body)
        pending = [item for item in plan if previous.get(delivery_key(item, sender)) not in ("accepted", "attempting", "uncertain")]
        for item in plan:
            if item not in pending:
                results.append({"email": item.email, "certificate": item.certificate, "status": "skipped_previous_or_uncertain"})
        if cancelled and cancelled():
            results.extend({"email": item.email, "certificate": item.certificate, "status": "not_attempted"} for item in pending)
            return journal, results
        if not pending:
            return journal, results
        with smtp_factory("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
            smtp.login(sender, password.replace(" ", ""))
            for index, item in enumerate(pending):
                if index >= limit or (cancelled and cancelled()):
                    results.extend({"email": i.email, "certificate": i.certificate, "status": "not_attempted"} for i in pending[index:])
                    break
                message = make_message(item, sender, subject, body)
                key = delivery_key(item, sender)
                if previous.get(key) in ("accepted", "attempting", "uncertain"):
                    results.append({"email": item.email, "certificate": item.certificate, "status": "skipped_previous_or_uncertain"})
                    continue
                log(item, key, "attempting")
                try:
                    refused = smtp.send_message(message, from_addr=sender, to_addrs=[item.email])
                    if refused:
                        results.append(log(item, key, "rejected"))
                    else:
                        results.append(log(item, key, "accepted"))
                except smtplib.SMTPRecipientsRefused as exc:
                    results.append(log(item, key, "rejected"))
                    throttled = any(400 <= code < 500 or b"quota" in str(reason).lower().encode()
                                    or b"limit" in str(reason).lower().encode()
                                    for code, reason in exc.recipients.values())
                    if throttled:
                        results.extend({"email": i.email, "certificate": i.certificate, "status": "not_attempted"} for i in pending[index + 1:])
                        break
                except Exception:
                    results.append(log(item, key, "uncertain"))
                    results.extend({"email": i.email, "certificate": i.certificate, "status": "not_attempted"} for i in pending[index + 1:])
                    break
                if progress:
                    progress(len(results), len(plan), results[-1]["status"])
                if index + 1 < min(limit, len(pending)):
                    time.sleep(pause_seconds)
        return journal, results
    finally:
        lock.unlink(missing_ok=True)
