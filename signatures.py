"""Visible signature-image placement using a unique labelled signature line."""
from dataclasses import replace

import pymupdf as fitz

from stamper import Placement, SIGNATURE_MARKER, check_area, page_bounds, stamp_labels

LABELS = ("Authorized Signature", "Authorised Signature", "Signature", "Signed by",
          "Authorized Signatory", "Authorised Signatory", "Principal", "Director", "Registrar")


def detect_signature(page, ocr=False, label=None):
    def result(rect, state, reason):
        return Placement(tuple(rect) if rect else None, state, reason, "signature")

    if any(SIGNATURE_MARKER in (a.info.get("subject", "") or "") for a in (page.annots() or [])):
        return result(None, "stamped", "A signature was already applied by this tool.")
    textpage = None
    if ocr and not page.get_text().strip():
        try:
            textpage = page.get_textpage_ocr(dpi=200, full=True)
        except Exception as exc:
            return result(None, "review", f"OCR unavailable: {exc}")
    anchors = stamp_labels(page, textpage, [label] if label else LABELS)
    if len(anchors) != 1:
        return result(None, "review", "No unique signatory label. Enter the intended role, or draw the signature area.")
    anchor = anchors[0]
    lines = []
    for drawing in page.get_drawings():
        if drawing.get("type") not in ("s", "fs"):
            continue
        for item in drawing.get("items", []):
            if item[0] == "l":
                a, b = item[1:3]
                if abs(a.y - b.y) <= 1 and 40 <= abs(a.x - b.x) <= 420:
                    lines.append((min(a.x, b.x), max(a.x, b.x), (a.y + b.y) / 2))
            elif item[0] == "re":
                r = fitz.Rect(item[1])
                if r.height <= 2 and 40 <= r.width <= 420:
                    lines.append((r.x0, r.x1, r.y0))
    # Some templates use underscore characters rather than vector lines.
    for word in page.get_text("words", textpage=textpage):
        if len(word[4]) >= 5 and set(word[4]) == {"_"}:
            lines.append((word[0], word[2], word[3] - 3))
    candidates = []
    for x0, x1, y in lines:
        center = (anchor.x0 + anchor.x1) / 2
        below_label = x0 - 10 <= center <= x1 + 10 and -12 <= anchor.y0 - y <= 35
        above_label = x0 - 10 <= center <= x1 + 10 and 0 <= y - anchor.y1 <= 45
        beside_label = 0 <= x0 - anchor.x1 <= 45 and abs(y - anchor.y1) <= 12
        if not (below_label or above_label or beside_label):
            continue
        top = y - 42
        if above_label:
            top = max(top, anchor.y1 + 3)
        rect = fitz.Rect(x0 + 3, top, x1 - 3, y - 3)
        if rect.height < 18 or not page_bounds(page).contains(rect):
            continue
        if not any(max(abs(a - b) for a, b in zip(rect, old)) < 3 for old in candidates):
            candidates.append(rect)
    if len(candidates) != 1:
        return result(None, "review", "No unique signature line next to the selected label. Draw the intended area.")
    checked = check_area(page, candidates[0], ignore_underline=True)
    reason = "Signature label and clear signature line detected." if checked.status == "ready" else checked.reason
    return replace(checked, kind="signature", reason=reason)
