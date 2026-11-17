import io
from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw

from stamper import (Placement, batch_export, check_area, detect, digest, discover,
                     export_one, inspect, selected_pages, stamp_bytes)


def certificate(path, ys=(350,), rotation=0, ink=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open() as doc:
        for y in ys:
            page = doc.new_page(width=595, height=842)
            page.insert_text((150, 80), "SAMPLE CERTIFICATE - TEST DATA", fontsize=15)
            page.insert_text((150, y), "College Stamp & Date:", fontsize=11)
            page.draw_rect(fitz.Rect(147, y + 10, 347, y + 100))
            if ink:
                page.draw_rect(fitz.Rect(190, y + 30, 290, y + 70), fill=(0.2, 0.2, 0.8))
            page.set_rotation(rotation)
        doc.save(path)
    return path


@pytest.fixture
def stamp(tmp_path):
    image = Image.new("RGBA", (300, 120), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((3, 3, 296, 116), outline=(0, 50, 180), width=5)
    draw.text((95, 50), "TEST STAMP", fill=(0, 50, 180))
    path = tmp_path / "stamp.png"
    image.save(path)
    return stamp_bytes(path)


def test_detects_independent_page_boxes(tmp_path):
    cert = inspect(certificate(tmp_path / "a.pdf", ys=(350, 510)))
    assert not cert.error
    assert [p.status for p in cert.pages] == ["ready", "ready"]
    assert cert.pages[1].rect[1] - cert.pages[0].rect[1] == 160


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_occupied_area_on_rotated_pages(tmp_path, rotation):
    cert = inspect(certificate(tmp_path / "occupied.pdf", rotation=rotation, ink=True))
    assert not cert.error
    assert cert.pages[0].status == "review"
    assert "ink" in cert.pages[0].reason


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_export_and_repeat_detection(tmp_path, stamp, rotation):
    source = tmp_path / "input"
    path = certificate(source / "Nairobi" / "a.pdf", ys=(350, 510), rotation=rotation)
    original = digest(path)
    cert = inspect(path)
    output = tmp_path / "output"
    status, sha = export_one(cert, source, output, stamp, "all")
    target = output / "Nairobi" / "a.pdf"
    assert status == "stamped" and sha == digest(target)
    assert digest(path) == original
    assert [p.status for p in inspect(target).pages] == ["stamped", "stamped"]
    with fitz.open(target) as doc:
        assert len(doc) == 2
        assert doc[0].rotation == rotation
        assert "SAMPLE CERTIFICATE" in doc[0].get_text()
    with pytest.raises(FileExistsError):
        export_one(cert, source, output, stamp, "all")


def test_changed_source_is_rejected(tmp_path, stamp):
    source = tmp_path / "input"
    path = certificate(source / "a.pdf")
    cert = inspect(path)
    path.write_bytes(path.read_bytes() + b"\n%changed")
    with pytest.raises(ValueError, match="changed"):
        export_one(cert, source, tmp_path / "out", stamp)


def test_uncertain_page_skips_whole_pdf(tmp_path, stamp):
    source = tmp_path / "input"
    cert = inspect(certificate(source / "a.pdf", ys=(350, 500)))
    cert.pages[1] = Placement(None, "review", "No label")
    state, _ = export_one(cert, source, tmp_path / "out", stamp, "all")
    assert state.startswith("skipped")
    assert not (tmp_path / "out" / "a.pdf").exists()


def test_nested_output_excluded_and_invalid_output_refused(tmp_path, stamp):
    source = tmp_path / "input"
    certificate(source / "a.PDF")
    output = source / "stamped"
    certificate(output / "already.pdf")
    paths = discover(source, output)
    assert len(paths) == 1
    cert = inspect(paths[0])
    with pytest.raises(ValueError):
        export_one(cert, source, source, stamp)
    with pytest.raises(ValueError):
        batch_export([cert], source, tmp_path, stamp)


def test_bad_pdf_does_not_abort_batch(tmp_path, stamp):
    source = tmp_path / "input"
    good = inspect(certificate(source / "a.pdf"))
    bad = source / "broken.pdf"
    bad.write_text("not a pdf")
    audit, report = batch_export([inspect(bad), good], source, tmp_path / "out", stamp)
    assert [r["status"] for r in report] == ["error", "stamped"]
    assert audit.exists()


def test_missing_anchor_and_password_require_review(tmp_path):
    path = tmp_path / "blank.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        assert detect(page).status == "review"
        doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    assert "Password" in inspect(path).error


def test_white_removal_and_transparent_stamp(tmp_path):
    path = tmp_path / "white.png"
    Image.new("RGB", (30, 30), "white").save(path)
    with pytest.raises(ValueError, match="transparent"):
        stamp_bytes(path, remove_white=True)
    assert stamp_bytes(path)


def test_cancel_is_accounted_for(tmp_path, stamp):
    source = tmp_path / "in"
    cert = inspect(certificate(source / "a.pdf"))
    _, rows = batch_export([cert], source, tmp_path / "out", stamp, cancelled=lambda: True)
    assert rows[0]["status"] == "cancelled"
