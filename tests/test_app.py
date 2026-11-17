"""Desktop integration smoke check (requires a display with Tcl/Tk)."""
import os
from pathlib import Path

import pytest

from stamper import inspect
from test_stamper import certificate, stamp


@pytest.fixture(scope="module")
def desktop_window():
    from app import App
    window = App()
    window.withdraw()
    yield window
    if window.import_session:
        window.import_session.cleanup()
    window.destroy()


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Desktop display required")
def test_preview_and_page_navigation(tmp_path, stamp, desktop_window):

    source = tmp_path / "input"
    cert = inspect(certificate(source / "a.pdf", ys=(350, 500), rotation=90))
    stamp_path = tmp_path / "stamp-preview.png"
    stamp_path.write_bytes(stamp)
    window = desktop_window
    try:
        window.source.set(str(source))
        window.stamp.set(str(stamp_path))
        window.certificates = [cert]
        window.current = cert
        window.tree.insert("", "end", iid="0", text="a.pdf")
        window.update_idletasks()
        window.preview()
        assert window.render_context is not None, window.detail.get()
        assert window.photo is not None
        window.turn(1)
        assert window.page_index == 1
        assert "Page 2/2" in window.detail.get()
        window.approve()
        assert window.certificate_state(cert) == "ready"
        window.mode.set("all")
        window.refresh_states()
        assert window.tree.item("0", "values") == ("ready",)
    finally:
        window.current = None
        window.tree.delete(*window.tree.get_children())


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Desktop display required")
def test_zip_import_populates_preview_and_states(tmp_path, monkeypatch, desktop_window):
    import zipfile
    from app import App, filedialog
    path = certificate(tmp_path / "input" / "a.pdf")
    archive = tmp_path / "regional.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.write(path, "Region/a.pdf")
    window = desktop_window
    try:
        monkeypatch.setattr(filedialog, "askopenfilenames", lambda **kwargs: (str(archive),))
        monkeypatch.setattr(window, "work", lambda fn: fn())
        window.choose_zip()
        window.poll()
        window.update_idletasks()
        assert len(window.certificates) == 1
        assert window.source_display.get() == "regional.zip"
        assert window.certificate_state(window.certificates[0]) == "ready"
        window.select()
        assert window.render_context is not None, window.detail.get()
    finally:
        if window.import_session:
            window.import_session.cleanup()
        window.import_session = None
        window.current = None
