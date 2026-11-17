import pymupdf as fitz
import pytest

from stamper import export_one, inspect
from test_stamper import stamp


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_blank_space_avoids_words_and_stamps(tmp_path, stamp, rotation):
    source = tmp_path / "input"
    source.mkdir()
    path = source / "no-field.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((350, 780), "TEXT AT THE BOTTOM RIGHT", fontsize=12)
        page.set_rotation(rotation)
        doc.save(path)
    cert = inspect(path, operation="blank-space")
    placement = cert.pages[0]
    assert placement.status == "ready", placement.reason
    with fitz.open(path) as doc:
        padded = fitz.Rect(placement.rect) + (-8, -8, 8, 8)
        assert not any(padded.intersects(fitz.Rect(w[:4])) for w in doc[0].get_text("words"))
    status, _ = export_one(cert, source, tmp_path / "out", stamp)
    assert status == "stamped"
    result = inspect(tmp_path / "out" / path.name, operation="blank-space")
    assert result.pages[0].status == "stamped"


def test_full_page_image_is_not_considered_clear():
    from blank_space import detect_blank_space
    with fitz.open() as doc:
        page = doc.new_page()
        page.draw_rect(page.rect, fill=(.7, .7, .7))
        assert detect_blank_space(page).status == "review"


def test_raster_content_is_avoided(tmp_path):
    from PIL import Image
    from blank_space import detect_blank_space
    image = tmp_path / "scanned.png"
    Image.new("RGB", (180, 100), "black").save(image)
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        blocked = fitz.Rect(360, 710, 580, 830)
        page.insert_image(blocked, filename=str(image))
        result = detect_blank_space(page)
        assert result.status == "ready"
        assert not fitz.Rect(result.rect).intersects(blocked)
