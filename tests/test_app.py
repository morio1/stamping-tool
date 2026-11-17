"""Desktop integration smoke check (requires a display with Tcl/Tk)."""
import os
from pathlib import Path

import pytest

from stamper import inspect
from test_stamper import certificate, stamp


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Desktop display required")
def test_preview_and_page_navigation(tmp_path, stamp):
    from app import App

    source = tmp_path / "input"
    cert = inspect(certificate(source / "a.pdf", ys=(350, 500), rotation=90))
    stamp_path = tmp_path / "stamp-preview.png"
    stamp_path.write_bytes(stamp)
    window = App()
    window.withdraw()
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
        window.destroy()
