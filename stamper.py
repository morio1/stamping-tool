"""Local, per-page PDF placement and non-destructive batch export."""
from __future__ import annotations

import hashlib
import io
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pymupdf as fitz
from PIL import Image

MARKER = "CertStampPro:v1"
SIGNATURE_MARKER = "CertSignaturePro:v1"
ANCHORS = ("College Stamp & Date", "College Stamp", "Stamp & Date", "Official Stamp",
           "Institution Stamp", "School Stamp", "Official Seal", "Seal", "Stamp")


@dataclass
class Placement:
    rect: tuple | None
    status: str
    reason: str
    kind: str = "stamp"


@dataclass
class Certificate:
    path: Path
    digest: str
    pages: list[Placement]
    error: str = ""
    operation: str = "stamp"


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stamp_bytes(path, opacity=0.9, remove_white=False):
    if not 0 < opacity <= 1:
        raise ValueError("Opacity must be greater than zero and at most one.")
    with Image.open(path) as source:
        image = source.convert("RGBA")
    # Optional white-paper removal preserves coloured ink and antialiasing.
    pixels = []
    for r, g, b, a in (image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()):
        if remove_white:
            a = round(a * (255 - min(r, g, b)) / 255)
        pixels.append((r, g, b, round(a * opacity)))
    image.putdata(pixels)
    if image.getbbox() is None:
        raise ValueError("The selected image is entirely transparent.")
    image = image.crop(image.getbbox())
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def page_bounds(page):
    return page.rect * page.derotation_matrix


def check_area(page, rect, ignore_underline=False):
    bounds = page_bounds(page)
    if rect.is_empty or rect.width < 18 or rect.height < 18 or not bounds.contains(rect):
        return Placement(None, "review", "Stamp box is too small or outside the page.")
    # Text in the proposed interior is never silently covered.
    interior = fitz.Rect(rect.x0 + 4, rect.y0 + 4, rect.x1 - 4, rect.y1 - 4)
    text = page.get_textbox(interior).strip()
    if ignore_underline:
        text = text.replace("_", "").strip()
    if text:
        return Placement(tuple(rect), "occupied", "Existing text or stamp occupies the box. Skipped to prevent covering it.")
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), clip=interior * page.rotation_matrix,
                          colorspace=fitz.csRGB, alpha=False)
    data = pix.samples
    total = max(1, pix.width * pix.height)
    dark = sum(min(data[i:i + 3]) < 200 for i in range(0, len(data), 3)) / total
    coloured = sum(max(data[i:i + 3]) - min(data[i:i + 3]) > 45
                   and min(data[i:i + 3]) < 190 for i in range(0, len(data), 3)) / total
    if dark > 0.025 or coloured > 0.004:
        return Placement(tuple(rect), "occupied", "Possible existing stamp, signature or other ink in the field. Skipped to prevent overlap.")
    return Placement(tuple(rect), "ready", "Label and empty stamp box detected.")


def vector_boxes(page):
    """Recognize closed paths AND boxes drawn as four independent dotted strokes."""
    boxes, horizontal, vertical = [], [], []
    max_width = min(600, page_bounds(page).width * 0.8)
    max_height = min(260, page_bounds(page).height * 0.45)
    for drawing in page.get_drawings():
        if drawing.get("type") not in ("s", "fs"):
            continue
        rect = fitz.Rect(drawing["rect"])
        if 40 <= rect.width <= max_width and 24 <= rect.height <= max_height:
            # A path bounding box alone is not proof of a rectangle.
            items = drawing.get("items", [])
            if any(item[0] == "re" for item in items):
                boxes.append(rect)
        for item in drawing.get("items", []):
            if item[0] != "l":
                continue
            a, b = item[1:3]
            if abs(a.y - b.y) < 1 and 40 <= abs(a.x - b.x) <= max_width:
                horizontal.append((min(a.x, b.x), max(a.x, b.x), (a.y + b.y) / 2))
            if abs(a.x - b.x) < 1 and 24 <= abs(a.y - b.y) <= max_height:
                vertical.append(((a.x + b.x) / 2, min(a.y, b.y), max(a.y, b.y)))
    for x0, x1, top in horizontal:
        for bx0, bx1, bottom in horizontal:
            if not (24 <= bottom - top <= max_height and abs(x0 - bx0) <= 3 and abs(x1 - bx1) <= 3):
                continue
            sides = [x for x, y0, y1 in vertical if abs(y0 - top) <= 3 and abs(y1 - bottom) <= 3]
            if any(abs(x - x0) <= 3 for x in sides) and any(abs(x - x1) <= 3 for x in sides):
                boxes.append(fitz.Rect(x0, top, max(x1, bx1), bottom))
    unique = []
    for rect in boxes:
        if not any(max(abs(a - b) for a, b in zip(rect, old)) < 3 for old in unique):
            unique.append(rect)
    return unique


def stamp_labels(page, textpage=None, labels=None):
    """Use word positions, tolerating nonstandard space glyphs in certificate PDFs."""
    import re
    words = page.get_text("words", textpage=textpage)
    lines = {}
    for word in words:
        lines.setdefault((word[5], word[6]), []).append(word)
    found = []
    for line in lines.values():
        line.sort(key=lambda w: w[0])
        normalized = [re.sub(r"[^a-z&]", "", w[4].lower()) for w in line]
        for phrase in labels or ANCHORS:
            tokens = [re.sub(r"[^a-z&]", "", t) for t in phrase.lower().split()]
            for i in range(len(line) - len(tokens) + 1):
                if normalized[i:i + len(tokens)] == tokens:
                    rect = fitz.Rect(line[i][:4])
                    for word in line[i + 1:i + len(tokens)]:
                        rect |= fitz.Rect(word[:4])
                    if not any(rect.intersects(old) for old in found):
                        found.append(rect)
    return found


def detect(page, ocr=False, labels=None):
    if any(MARKER in (a.info.get("subject", "") or "") for a in (page.annots() or [])):
        return Placement(None, "stamped", "Previously stamped by this tool.")
    textpage = None
    if ocr and not page.get_text().strip():
        try:
            textpage = page.get_textpage_ocr(dpi=200, full=True)
        except Exception as exc:
            return Placement(None, "review", f"OCR unavailable: {exc}")
    anchors = stamp_labels(page, textpage, labels)
    if len(anchors) != 1:
        return Placement(None, "review", "No unique stamp label found. Draw the stamp box in preview.")
    anchor = anchors[0]
    candidates = []
    for r in vector_boxes(page):
        label_gap = max(35, min(80, r.width * 0.45))
        label_left = 0 <= r.x0 - anchor.x1 <= label_gap and r.y0 <= (anchor.y0 + anchor.y1) / 2 <= r.y1
        label_above_below = (r.x0 - 30 <= anchor.x0 <= r.x1
                            and r.y0 - 35 <= anchor.y0 <= r.y1 + 25)
        if label_left or label_above_below:
            # A label inside a box gets its own reserved band.
            if r.intersects(anchor):
                if anchor.y0 < r.y0 + r.height / 2:
                    r.y0 = anchor.y1 + 5
                else:
                    r.y1 = anchor.y0 - 5
            r = fitz.Rect(r.x0 + 5, r.y0 + 5, r.x1 - 5, r.y1 - 5)
            if r.width >= 30 and r.height >= 24:
                candidates.append(r)
    if candidates:
        # A visible stamp may itself have a rectangular border inside the field.
        # Use the enclosing field so its existing ink is checked, not a false ambiguity.
        enclosing = [r for r in candidates if all(r.contains(other) for other in candidates)]
        if len(enclosing) == 1:
            return check_area(page, enclosing[0])
    # Suggest an area but require review: a text anchor alone is insufficient proof.
    bounds = page_bounds(page)
    proposed = fitz.Rect(anchor.x0, anchor.y1 + 6,
                         min(bounds.x1 - 10, anchor.x0 + 185),
                         min(bounds.y1 - 10, anchor.y1 + 86))
    return Placement(tuple(proposed) if not proposed.is_empty else None,
                     "review", "Label found, but no unique vector box. Check or redraw the suggested area.")


def inspect(path, ocr=False, operation="stamp", label=None):
    path = Path(path)
    try:
        if operation not in ("stamp", "signature", "blank-space"):
            raise ValueError("Unknown certificate operation")
        before = digest(path)
        with fitz.open(path) as doc:
            if doc.needs_pass:
                raise ValueError("Password-protected PDF")
            if not len(doc):
                raise ValueError("Empty PDF")
            if doc.get_sigflags() > 0:
                raise ValueError("Digitally signed PDF: stamping would invalidate signatures")
            if operation == "blank-space":
                from blank_space import detect_blank_space
                pages = [detect_blank_space(page) for page in doc]
            elif operation == "signature":
                from signatures import detect_signature
                pages = [detect_signature(page, ocr, label) for page in doc]
            else:
                pages = [detect(page, ocr, [label] if label else None) for page in doc]
        if digest(path) != before:
            raise ValueError("File changed during analysis; scan again")
        return Certificate(path, before, pages, operation=operation)
    except Exception as exc:
        return Certificate(path, "", [], str(exc), operation)


def discover(root, output=None):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Certificate folder does not exist")
    output = Path(output).resolve() if output else None
    return sorted(p for p in root.rglob("*") if p.suffix.lower() == ".pdf"
                  and p.is_file() and not p.is_symlink()
                  and p.resolve().is_relative_to(root)
                  and not (output and p.resolve().is_relative_to(output)))


def selected_pages(cert, mode):
    if mode not in ("first", "last", "all"):
        raise ValueError("Page selection must be first, last or all")
    if not cert.pages:
        raise ValueError("Certificate has no readable pages")
    if mode == "first":
        return [0]
    if mode == "last":
        return [len(cert.pages) - 1]
    return list(range(len(cert.pages)))


def batch_preflight(certificates, source, output, mode="first", require_approval=False):
    """Count full-document decisions before any output is written."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source.is_relative_to(output):
        raise ValueError("Choose an output folder separate from input and its parents")
    counts = dict(total=len(certificates), ready=0, review=0, occupied=0,
                  already_applied=0, errors=0, existing_output=0)
    for cert in certificates:
        if cert.error:
            counts["errors"] += 1
            continue
        relative = cert.path.resolve().relative_to(source)
        if (output / relative).exists():
            counts["existing_output"] += 1
            continue
        states = [cert.pages[i].status for i in selected_pages(cert, mode)]
        if any(s == "occupied" for s in states):
            key = "occupied"
        elif any(s == "stamped" for s in states):
            key = "already_applied"
        elif all(s == "approved" or (s == "ready" and not require_approval) for s in states):
            key = "ready"
        else:
            key = "review"
        counts[key] += 1
    return counts


def apply_stamp(page, placement, image):
    rect = fitz.Rect(placement.rect)
    if not page_bounds(page).contains(rect) or rect.is_empty:
        raise ValueError("Invalid stamp coordinates")
    page.insert_image(rect, stream=image, keep_proportion=True, overlay=True)
    annotation = page.add_rect_annot(rect)
    marker = SIGNATURE_MARKER if placement.kind == "signature" else MARKER
    annotation.set_info(subject=marker, content=f"{placement.kind.title()} applied using Cert Stamp Pro")
    annotation.set_border(width=0)
    annotation.set_flags(fitz.PDF_ANNOT_IS_HIDDEN)
    annotation.update()


def export_one(cert, source, output, image, mode="first"):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source.is_relative_to(output):
        raise ValueError("Choose an output folder separate from the input folder or its parents")
    relative = cert.path.resolve().relative_to(source)
    target = output / relative
    if not target.resolve().is_relative_to(output):
        raise ValueError("Output path escapes the selected output folder")
    if target.exists():
        raise FileExistsError(f"Output already exists: {relative}")
    if cert.error:
        raise ValueError(cert.error)
    indices = selected_pages(cert, mode)
    if any(cert.pages[i].kind != cert.operation for i in indices):
        raise ValueError("Placement belongs to another module; scan again")
    if any(cert.pages[i].status not in ("ready", "approved") for i in indices):
        return "skipped: selected page needs review or is already stamped", None
    if digest(cert.path) != cert.digest:
        raise ValueError("Source changed since analysis; scan again")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{uuid.uuid4().hex}.tmp")
    try:
        with fitz.open(cert.path) as doc:
            for i in indices:
                apply_stamp(doc[i], cert.pages[i], image)
            doc.save(temp, garbage=3, deflate=True)
        with fitz.open(temp) as verified:
            if len(verified) != len(cert.pages):
                raise ValueError("Export verification failed")
        # Hard-link publication is atomic and refuses to overwrite existing files.
        os.link(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return ("signed" if cert.operation == "signature" else "stamped"), digest(target)


def batch_export(certificates, source, output, image, mode="first", progress=None, cancelled=None):
    output = Path(output).resolve()
    source = Path(source).resolve()
    if output == source or source.is_relative_to(output):
        raise ValueError("Output must be separate from the input folder or its parents")
    output.mkdir(parents=True, exist_ok=True)
    report = []
    for index, cert in enumerate(certificates):
        if cancelled and cancelled():
            report.extend({"file": str(c.path.resolve().relative_to(source)), "status": "cancelled"}
                          for c in certificates[index:])
            break
        entry = {"file": str(cert.path.resolve().relative_to(source)), "source_sha256": cert.digest,
                 "operation": cert.operation,
                 "placements": [asdict(p) for p in cert.pages]}
        try:
            entry["status"], entry["output_sha256"] = export_one(cert, source, output, image, mode)
        except Exception as exc:
            entry.update(status="error", error=str(exc))
        report.append(entry)
        if progress:
            progress(index + 1, len(certificates), entry["status"])
    audit = output / f"audit-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.json"
    audit.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return audit, report
