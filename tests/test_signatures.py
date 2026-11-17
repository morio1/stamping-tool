import pymupdf as fitz
import pytest

from stamper import apply_stamp, detect, export_one, inspect
from signatures import detect_signature
from test_stamper import stamp


def signature_certificate(path, role="Principal", second=False, occupied=False, rotation=0, underline=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((70, 60), "SAMPLE CERTIFICATE", fontsize=20)
        page.insert_text((90, 470), role, fontsize=10)
        if underline:
            page.insert_text((70, 450), "________________________", fontsize=10)
        else:
            page.draw_line((70, 450), (240, 450))
        if second:
            page.insert_text((350, 470), "Registrar", fontsize=10)
            page.draw_line((320, 450), (490, 450))
        if occupied:
            page.draw_line((100, 425), (190, 435), color=(0, 0, 0.5), width=3)
        page.set_rotation(rotation)
        doc.save(path)
    return path


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_signature_line_placement_and_export(tmp_path, stamp, rotation):
    source = tmp_path / "input"
    path = signature_certificate(source / "Region" / "a.pdf", rotation=rotation)
    cert = inspect(path, operation="signature")
    assert cert.operation == "signature"
    assert cert.pages[0].status == "ready", cert.pages[0].reason
    assert cert.pages[0].kind == "signature"
    assert cert.pages[0].rect == pytest.approx((73, 408, 237, 447))
    state, _ = export_one(cert, source, tmp_path / "out", stamp)
    assert state == "signed"
    result = tmp_path / "out" / "Region" / "a.pdf"
    assert inspect(result, operation="signature").pages[0].status == "stamped"
    assert inspect(result, operation="stamp").pages[0].status != "stamped"


def test_multiple_signatories_need_role_selection(tmp_path):
    path = signature_certificate(tmp_path / "a.pdf", second=True)
    assert inspect(path, operation="signature").pages[0].status == "review"
    result = inspect(path, operation="signature", label="Registrar")
    assert result.pages[0].status == "ready"
    assert result.pages[0].rect[0] == 323


def test_occupied_signature_is_not_automatic(tmp_path):
    path = signature_certificate(tmp_path / "a.pdf", occupied=True)
    assert inspect(path, operation="signature").pages[0].status == "occupied"


def test_text_underline_supported(tmp_path):
    path = signature_certificate(tmp_path / "a.pdf", underline=True)
    result = inspect(path, operation="signature")
    assert result.pages[0].status == "ready", result.pages[0].reason


def test_unlabelled_line_is_not_assumed_signature():
    with fitz.open() as doc:
        page = doc.new_page()
        page.draw_line((70, 450), (240, 450))
        assert detect_signature(page).status == "review"


def test_custom_role_and_new_stamp_brand():
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((90, 470), "Training Lead", fontsize=10)
        page.draw_line((70, 450), (240, 450))
        assert detect_signature(page, label="Training Lead").status == "ready"
        page.insert_text((300, 370), "Assessment Approval", fontsize=10)
        page.draw_rect(fitz.Rect(295, 385, 520, 475))
        assert detect(page, labels=["Assessment Approval"]).status == "ready"


def test_two_lines_for_same_role_require_review():
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((90, 470), "Principal", fontsize=10)
        page.draw_line((70, 450), (240, 450))
        page.draw_line((70, 440), (240, 440))
        assert detect_signature(page).status == "review"


def test_stamp_does_not_block_signature(tmp_path, stamp):
    path = signature_certificate(tmp_path / "a.pdf")
    with fitz.open(path) as doc:
        from stamper import Placement
        apply_stamp(doc[0], Placement((300, 600, 480, 680), "ready", "test"), stamp)
        output = tmp_path / "with-stamp.pdf"
        doc.save(output)
    assert inspect(output, operation="signature").pages[0].status == "ready"


def test_signature_can_be_above_label_and_below_heading():
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((90, 400), "Signature", fontsize=10)
        page.draw_line((70, 445), (240, 445))
        assert detect_signature(page).status == "ready"
