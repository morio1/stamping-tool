import stat
import zipfile

import pytest

from archives import ImportCancelled, extract_pdfs, import_archives, package_results
from stamper import batch_export, discover, inspect
from test_stamper import certificate, stamp


def test_zip_batch_preserves_regions_and_exports_only_current_results(tmp_path, stamp):
    path = certificate(tmp_path / "original" / "Regional Centre" / "a.pdf")
    source_zip = tmp_path / "certificates.zip"
    with zipfile.ZipFile(source_zip, "w") as z:
        z.write(path, "Regional Centre/a.pdf")
        z.writestr("notes.txt", "not a certificate")
    session, root = import_archives([source_zip])
    try:
        files = discover(root)
        assert len(files) == 1
        output = tmp_path / "output"
        audit, report = batch_export([inspect(files[0])], root, output, stamp)
        (output / "stale.pdf").write_bytes(b"old")
        result = package_results(output, report, audit)
        with zipfile.ZipFile(result) as z:
            assert sorted(z.namelist()) == sorted(["Regional Centre/a.pdf", audit.name])
            assert z.testzip() is None
        with pytest.raises(FileExistsError):
            package_results(output, report, audit, result)
    finally:
        session.cleanup()


@pytest.mark.parametrize("name", ["../a.pdf", "/a.pdf", "C:/a.pdf", "x/../../a.pdf", "NUL.pdf", "a?.pdf"])
def test_unsafe_zip_rejected(tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(name, b"data")
    with pytest.raises(ValueError):
        extract_pdfs(archive, tmp_path / "extract")
    assert not list((tmp_path / "extract").rglob("*.pdf"))


def test_duplicate_zip_paths_and_limits(tmp_path):
    archive = tmp_path / "dup.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("A.pdf", b"1234")
        z.writestr("a.PDF", b"5678")
    with pytest.raises(ValueError, match="duplicate"):
        extract_pdfs(archive, tmp_path / "out")
    with pytest.raises(ValueError, match="entry limit"):
        extract_pdfs(archive, tmp_path / "out", max_files=1)
    archive = tmp_path / "big.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("big.pdf", b"a" * 1000)
    with pytest.raises(ValueError, match="size limit"):
        extract_pdfs(archive, tmp_path / "out", max_bytes=100)


def test_existing_files_are_never_removed(tmp_path):
    target = tmp_path / "out"
    target.mkdir()
    (target / "a.pdf").write_bytes(b"original")
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("a.pdf", b"new")
    with pytest.raises(FileExistsError):
        extract_pdfs(archive, target)
    assert (target / "a.pdf").read_bytes() == b"original"


def test_multiple_archives_same_name_and_cancel(tmp_path):
    archives = []
    for folder in ("one", "two"):
        parent = tmp_path / folder
        parent.mkdir()
        archive = parent / "same.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("a.pdf", b"pdf")
        archives.append(archive)
    session, root = import_archives(archives)
    try:
        assert len(discover(root)) == 2
    finally:
        session.cleanup()
    with pytest.raises(ImportCancelled):
        import_archives(archives, cancelled=lambda: True)


def test_symlink_zip_rejected(tmp_path):
    archive = tmp_path / "link.zip"
    with zipfile.ZipFile(archive, "w") as z:
        info = zipfile.ZipInfo("link.pdf")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, "../elsewhere")
    with pytest.raises(ValueError, match="symbolic"):
        extract_pdfs(archive, tmp_path / "out")
