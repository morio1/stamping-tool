import pymupdf as fitz
import pytest

from stamper import detect, inspect, export_one
from test_stamper import stamp


def dotted_certificate(path, units=6, y=312, occupied=False, rotation=0):
    with fitz.open() as doc:
        page = doc.new_page(width=842, height=595)
        page.insert_text((61, y + 40), "College Stamp & Date:", fontsize=7)
        for index in range(units):
            page.insert_text((80, 100 + index * 13), f"9101/{101 + index} SAMPLE UNIT", fontsize=7)
        for a, b in [((150, y), (332, y)), ((150, y + 73), (332, y + 73)),
                     ((150, y), (150, y + 72.3)), ((332, y), (332, y + 72.3))]:
            page.draw_line(a, b, width=0.73, dashes="[.73 1.45] .73")
        if occupied:
            page.draw_rect(fitz.Rect(170, y + 15, 310, y + 60), color=(0.1, 0.2, 0.7), width=2)
        page.set_rotation(rotation)
        doc.save(path)


@pytest.mark.parametrize("units,y", [(1, 310), (2, 245), (3, 330), (4, 260), (5, 350), (6, 312), (7, 385)])
def test_one_to_seven_units_follow_actual_box(tmp_path, units, y):
    path = tmp_path / "sample.pdf"
    dotted_certificate(path, units=units, y=y)
    result = inspect(path)
    assert not result.error
    placement = result.pages[0]
    assert placement.status == "ready", placement.reason
    assert placement.rect == pytest.approx((155, y + 5, 327, y + 68), abs=0.1)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_existing_stamp_in_dotted_box_is_skipped(tmp_path, stamp, rotation):
    source = tmp_path / "input"
    source.mkdir()
    path = source / "already.pdf"
    dotted_certificate(path, occupied=True, rotation=rotation)
    result = inspect(path)
    assert result.pages[0].status == "occupied"
    state, _ = export_one(result, source, tmp_path / "out", stamp)
    assert state.startswith("skipped")
    assert not (tmp_path / "out" / "already.pdf").exists()


def test_two_sides_do_not_claim_box(tmp_path):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((61, 350), "College Stamp & Date:", fontsize=7)
        page.draw_line((150, 312), (332, 312))
        page.draw_line((150, 385), (332, 385))
        assert detect(page).status == "review"
