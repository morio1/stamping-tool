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
ANCHORS = ("College Stamp & Date", "College Stamp", "Stamp & Date", "Official Stamp")


@dataclass
class Placement:
    rect: tuple | None
    status: str
    reason: str


@dataclass
class Certificate:
    path: Path
    digest: str
    pages: list[Placement]
    error: str = ""


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
        raise ValueError("The selected stamp image is entirely transparent.")
    image = image.crop(image.getbbox())
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def page_bounds(page):
    return page.rect * page.derotation_matrix


def check_area(page, rect):
    bounds = page_bounds(page)
    if rect.is_empty or rect.width < 18 or rect.height < 18 or not bounds.contains(rect):
        return Placement(None, "review", "Stamp box is too small or outside the page.")
    # Text in the proposed interior is never silently covered.
    interior = fitz.Rect(rect.x0 + 4, rect.y0 + 4, rect.x1 - 4, rect.y1 - 4)
    if page.get_textbox(interior).strip():
        return Placement(tuple(rect), "review", "Text occupies the proposed box; draw a clear area.")
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), clip=interior * page.rotation_matrix,
                          colorspace=fitz.csRGB, alpha=False)
    data = pix.samples
    total = max(1, pix.width * pix.height)
    dark = sum(min(data[i:i + 3]) < 200 for i in range(0, len(data), 3)) / total
    if dark > 0.025:
        return Placement(tuple(rect), "review", "Existing ink or image content detected; inspect before approving.")
    return Placement(tuple(rect), "ready", "Label and empty stamp box detected.")


def detect(page, ocr=False):
    if any(MARKER in (a.info.get("subject", "") or "") for a in (page.annots() or [])):
        return Placement(None, "stamped", "Previously stamped by this tool.")
    textpage = None
    if ocr and not page.get_text().strip():
        try:
            textpage = page.get_textpage_ocr(dpi=200, full=True)
        except Exception as exc:
            return Placement(None, "review", f"OCR unavailable: {exc}")
    anchors = []
    for phrase in ANCHORS:
        for r in page.search_for(phrase, textpage=textpage):
            if not any(r.intersects(old) for old in anchors):
                anchors.append(r)
    if len(anchors) != 1:
        return Placement(None, "review", "No unique stamp label found. Draw the stamp box in preview.")
    anchor = anchors[0]
    candidates = []
    for drawing in page.get_drawings():
        r = fitz.Rect(drawing["rect"])
        if not (60 <= r.width <= 320 and 30 <= r.height <= 180):
            continue
        near_x = r.x0 - 30 <= anchor.x0 <= r.x1 + 30
        near_y = r.y0 - 45 <= anchor.y0 <= r.y1 + 30
        if near_x and near_y:
            # A label inside a box gets its own reserved band.
            if r.intersects(anchor):
                if anchor.y0 < r.y0 + r.height / 2:
                    r.y0 = anchor.y1 + 5
                else:
                    r.y1 = anchor.y0 - 5
            r = fitz.Rect(r.x0 + 5, r.y0 + 5, r.x1 - 5, r.y1 - 5)
            if r.width >= 30 and r.height >= 24:
                candidates.append(r)
    if len(candidates) == 1:
        return check_area(page, candidates[0])
    # Suggest an area but require review: a text anchor alone is insufficient proof.
    bounds = page_bounds(page)
    proposed = fitz.Rect(anchor.x0, anchor.y1 + 6,
                         min(bounds.x1 - 10, anchor.x0 + 185),
                         min(bounds.y1 - 10, anchor.y1 + 86))
    return Placement(tuple(proposed) if not proposed.is_empty else None,
                     "review", "Label found, but no unique vector box. Check or redraw the suggested area.")


def inspect(path, ocr=False):
    path = Path(path)
    try:
        before = digest(path)
        with fitz.open(path) as doc:
            if doc.needs_pass:
                raise ValueError("Password-protected PDF")
            if not len(doc):
                raise ValueError("Empty PDF")
            if doc.get_sigflags() > 0:
                raise ValueError("Digitally signed PDF: stamping would invalidate signatures")
            pages = [detect(page, ocr) for page in doc]
        if digest(path) != before:
            raise ValueError("File changed during analysis; scan again")
        return Certificate(path, before, pages)
    except Exception as exc:
        return Certificate(path, "", [], str(exc))


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


def apply_stamp(page, placement, image):
    rect = fitz.Rect(placement.rect)
    if not page_bounds(page).contains(rect) or rect.is_empty:
        raise ValueError("Invalid stamp coordinates")
    page.insert_image(rect, stream=image, keep_proportion=True, overlay=True)
    annotation = page.add_rect_annot(rect)
    annotation.set_info(subject=MARKER, content="Stamped using Cert Stamp Pro")
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
    return "stamped", digest(target)


def batch_export(certificates, source, output, image, mode="first", progress=None, cancelled=None):
    output = Path(output).resolve()
    source = Path(source).resolve()
    if output == source or source.is_relative_to(output):
        raise ValueError("Output must be separate from the input folder or its parents")
    output.mkdir(parents=True, exist_ok=True)
    report = []
    for index, cert in enumerate(certificates):
        if cancelled and cancelled():
            report.extend({"file": str(c.path.relative_to(source)), "status": "cancelled"}
                          for c in certificates[index:])
            break
        entry = {"file": str(cert.path.relative_to(source)), "source_sha256": cert.digest,
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
