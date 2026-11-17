from stamper import Certificate, Placement, batch_preflight


def test_preflight_counts_every_certificate_and_selected_page(tmp_path):
    source, output = tmp_path / "input", tmp_path / "output"
    source.mkdir()
    output.mkdir()
    certs = []
    for name, state in [("ready", "ready"), ("approved", "approved"), ("unclear", "review"),
                        ("occupied", "occupied"), ("done", "stamped"), ("exists", "ready")]:
        path = source / f"{name}.pdf"
        path.write_bytes(b"test")
        certs.append(Certificate(path, "test", [Placement((10, 10, 100, 100), state, "test")]))
    certs.append(Certificate(source / "broken.pdf", "", [], "Unreadable PDF"))
    (output / "exists.pdf").write_bytes(b"do not replace")
    counts = batch_preflight(certs, source, output)
    assert counts == dict(total=7, ready=2, review=1, occupied=1,
                          already_applied=1, errors=1, existing_output=1)
    assert sum(v for k, v in counts.items() if k != "total") == counts["total"]
    approved_only = batch_preflight(certs, source, output, require_approval=True)
    assert approved_only["ready"] == 1 and approved_only["review"] == 2
    assert (output / "exists.pdf").read_bytes() == b"do not replace"


def test_preflight_does_not_ignore_uncertain_selected_pages(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    cert = Certificate(source / "multi.pdf", "test", [
        Placement((10, 10, 100, 100), "ready", "test"),
        Placement(None, "review", "No unique field")])
    assert batch_preflight([cert], source, tmp_path / "out", "first")["ready"] == 1
    assert batch_preflight([cert], source, tmp_path / "out", "all")["review"] == 1
