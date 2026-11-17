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


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Desktop display required")
def test_signature_preview_approval_and_zip_export(tmp_path, stamp, desktop_window, monkeypatch):
    from app import messagebox
    from test_signatures import signature_certificate
    window = desktop_window
    window.operation.set("signature")
    window.field_label.set("Principal")
    window.reset_analysis()


    source = tmp_path / "input"
    path = signature_certificate(source / "a.pdf")
    image = tmp_path / "signature.png"
    image.write_bytes(stamp)
    window.source.set(str(source))
    window.output.set(str(tmp_path / "signed"))
    window.signature.set(str(image))
    window.require_approval.set(True)
    window.certificates = [inspect(path, operation="signature", label="Principal")]
    window.current = window.certificates[0]
    window.tree.insert("", "end", iid="0", text="a.pdf")
    window.preview()
    assert window.render_context is not None, window.detail.get()
    monkeypatch.setattr(window, "work", lambda fn: fn())
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **kw: None)
    window.export()
    window.poll()
    assert not (tmp_path / "signed" / "a.pdf").exists()
    window.approve()
    window.export()
    window.poll()
    assert inspect(tmp_path / "signed" / "a.pdf", operation="signature").pages[0].status == "stamped"
    import zipfile
    names = []
    for archive in tmp_path.glob("signed-*.zip"):
        with zipfile.ZipFile(archive) as zipped:
            names.extend(zipped.namelist())
    assert "a.pdf" in names
    window.operation.set("stamp")
    window.field_label.set("")
    window.require_approval.set(False)
    window.reset_analysis()


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Desktop display required")
def test_blank_space_module_preview(tmp_path, stamp, desktop_window):
    import pymupdf as fitz
    window = desktop_window
    window.operation.set("blank-space")
    window.reset_analysis()


    path = tmp_path / "certificate.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 100), "CERTIFICATE WITHOUT A STAMP FIELD", fontsize=12)
        doc.save(path)
    image = tmp_path / "stamp.png"
    image.write_bytes(stamp)
    window.stamp.set(str(image))
    window.current = inspect(path, operation="blank-space")
    window.preview()
    assert window.current.pages[0].status == "ready"
    assert window.render_context is not None, window.detail.get()
    window.operation.set("stamp")
    window.reset_analysis()


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Desktop display required")
def test_email_workspace_opens_without_connecting(desktop_window):
    window = desktop_window
    window.open_email()
    assert window.email_window.winfo_exists()
    assert not window.email_window.busy and window.email_window.plan == []
    assert window.email_window.password.get() == ""
    window.email_window.destroy()
    window.email_window = None
