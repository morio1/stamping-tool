import csv
import json
import smtplib

import pytest

from email_delivery import load_plan, make_message, send_batch
from stamper import batch_export, inspect
from test_stamper import certificate, stamp


class FakeSMTP:
    messages = []
    fail = False
    def __init__(self, host, port, **kwargs):
        assert host == "smtp.gmail.com" and port == 465
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def login(self, user, password): pass
    def send_message(self, message, from_addr, to_addrs):
        self.messages.append((message, to_addrs))
        if self.fail: raise smtplib.SMTPServerDisconnected("uncertain connection")
        return {}


@pytest.fixture
def email_plan(tmp_path, stamp):
    source, output = tmp_path / "input", tmp_path / "out"
    paths = [certificate(source / "Region" / f"{i}.pdf", ys=(350+i*20,)) for i in range(2)]
    audit, _ = batch_export([inspect(p) for p in paths], source, output, stamp)
    mapping = tmp_path / "recipients.csv"
    with mapping.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["email", "certificate", "recipient_name"])
        writer.writerow(["student1@example.test", "Region/0.pdf", "Student One"])
        writer.writerow(["student2@example.test", "Region/1.pdf", "Student Two"])
    return load_plan(mapping, output, audit), output, audit, mapping


def test_one_recipient_gets_only_their_verified_pdf(email_plan):
    plan, output, _, _ = email_plan
    FakeSMTP.messages, FakeSMTP.fail = [], False
    journal, rows = send_batch(plan, "sender@example.test", "not-a-real-password", "Certificate for {name}",
                               "Dear {name}, attached is {certificate}.", output,
                               reviewed=True, pause_seconds=0, smtp_factory=FakeSMTP)
    assert [r["status"] for r in rows] == ["accepted", "accepted"]
    for (message, recipients), item in zip(FakeSMTP.messages, plan):
        assert recipients == [item.email] and message["To"] == item.email
        attachments = list(message.iter_attachments())
        assert len(attachments) == 1
        assert attachments[0].get_payload(decode=True) == item.path.read_bytes()
    assert "not-a-real-password" not in journal.read_text()
    send_batch(plan, "sender@example.test", "unused", "Subject", "Body", output,
               reviewed=True, pause_seconds=0, smtp_factory=FakeSMTP)
    assert len(FakeSMTP.messages) == 2


def test_review_and_changed_attachment_block_sending(email_plan):
    plan, output, _, _ = email_plan
    with pytest.raises(ValueError, match="Review"):
        send_batch(plan, "sender@example.test", "unused", "Subject", "Body", output, smtp_factory=FakeSMTP)
    FakeSMTP.messages = []
    plan[0].path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        send_batch(plan, "sender@example.test", "unused", "Subject", "Body", output,
                   reviewed=True, smtp_factory=FakeSMTP)
    assert not FakeSMTP.messages


def test_uncertain_send_is_not_automatically_retried(email_plan):
    plan, output, _, _ = email_plan
    FakeSMTP.messages, FakeSMTP.fail = [], True
    _, rows = send_batch(plan, "sender@example.test", "unused", "Subject", "Body", output,
                         reviewed=True, pause_seconds=0, smtp_factory=FakeSMTP)
    assert rows[0]["status"] == "uncertain" and rows[1]["status"] == "not_attempted"
    FakeSMTP.fail = False
    send_batch(plan, "sender@example.test", "unused", "Subject", "Body", output,
               reviewed=True, pause_seconds=0, smtp_factory=FakeSMTP)
    assert len(FakeSMTP.messages) == 2
    assert FakeSMTP.messages[-1][1] == ["student2@example.test"]


def test_duplicate_and_wrong_certificate_mapping_rejected(email_plan):
    _, output, audit, mapping = email_plan
    mapping.write_text("email,certificate\na@example.test,../outside.pdf\n")
    with pytest.raises(ValueError): load_plan(mapping, output, audit)
    mapping.write_text("email,certificate\na@example.test,Region/0.pdf\na@example.test,Region/0.pdf\n")
    with pytest.raises(ValueError, match="duplicate"): load_plan(mapping, output, audit)


def test_batch_limit_and_cancel_do_not_send_remaining(email_plan):
    plan, output, _, _ = email_plan
    FakeSMTP.messages, FakeSMTP.fail = [], False
    _, rows = send_batch(plan, "sender@example.test", "unused", "Subject", "Body", output,
                         reviewed=True, limit=1, pause_seconds=0, smtp_factory=FakeSMTP)
    assert len(FakeSMTP.messages) == 1 and rows[-1]["status"] == "not_attempted"


def test_quota_refusal_stops_instead_of_trying_every_recipient(email_plan):
    plan, output, _, _ = email_plan
    class QuotaSMTP(FakeSMTP):
        messages = []
        def send_message(self, message, from_addr, to_addrs):
            self.messages.append(message)
            raise smtplib.SMTPRecipientsRefused({to_addrs[0]: (452, b"Quota limit")})
    _, rows = send_batch(plan, "sender@example.test", "unused", "Subject", "Body", output,
                         reviewed=True, pause_seconds=0, smtp_factory=QuotaSMTP)
    assert len(QuotaSMTP.messages) == 1
    assert [r["status"] for r in rows] == ["rejected", "not_attempted"]


def test_generated_template_relative_prefix_is_supported(email_plan):
    plan, output, audit, mapping = email_plan
    mapping.write_text("email,certificate,recipient_name\nstudent1@example.test,./Region/0.pdf,Student One\n")
    assert load_plan(mapping, output, audit)[0].sha256 == plan[0].sha256
