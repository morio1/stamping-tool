"""Find a conservative, text-free and visibly clear region without a stamp label."""
import pymupdf as fitz
from PIL import Image

from stamper import MARKER, Placement


def detect_blank_space(page):
    if any(MARKER in (a.info.get("subject", "") or "") for a in (page.annots() or [])):
        return Placement(None, "stamped", "A stamp was already applied by this tool.", "blank-space")
    display = page.rect
    margin, clearance = 24, 8
    width, height = min(170, display.width * .28), min(70, display.height * .13)
    if width < 60 or height < 28 or display.width < width + margin * 2 or display.height < height + margin * 2:
        return Placement(None, "review", "Page is too small for an automatic clear-space stamp.", "blank-space")
    words = [fitz.Rect(w[:4]) for w in page.get_text("words")]
    # Raster checking also catches scanned text, lines, logos, images and annotations.
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csRGB, alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    occupied = image.convert("L").point(lambda value: 255 if value < 245 else 0)
    right, bottom = display.width - margin - width, display.height - margin - height
    locations = [(right, bottom), (margin, bottom)]
    for y in range(int(bottom), margin - 1, -18):
        for x in range(int(right), margin - 1, -18):
            locations.append((x, y))
    for x, y in locations:
        candidate = fitz.Rect(x, y, x + width, y + height)
        padded = candidate + (-clearance, -clearance, clearance, clearance)
        rect = candidate * page.derotation_matrix
        padded_unrotated = padded * page.derotation_matrix
        if any(word.intersects(padded_unrotated) for word in words):
            continue
        pixels = occupied.crop((int(padded.x0), int(padded.y0), int(padded.x1 + 1), int(padded.y1 + 1)))
        if pixels.getbbox() is not None:
            continue
        return Placement(tuple(rect), "ready",
                         "Clear space found with an 8-point buffer; no extracted words or visible marks detected. Check its visual suitability.",
                         "blank-space")
    return Placement(None, "review", "No sufficiently clear area found. Draw and review a suitable area; nothing will be stamped automatically.", "blank-space")
