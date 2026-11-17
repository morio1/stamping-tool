"""Streaming ZIP import/export with bounded extraction and preserved PDF folders."""
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath


class ImportCancelled(Exception):
    pass


def extract_pdfs(archive, destination, progress=None, cancelled=None,
                 max_bytes=20 * 1024**3, max_files=100000):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    total_bytes, seen, files = 0, set(), []
    with zipfile.ZipFile(archive) as source:
        infos = source.infolist()
        if len(infos) > max_files:
            raise ValueError(f"ZIP exceeds the {max_files:,} entry limit")
        # Validate the complete archive before writing anything.
        for info in infos:
            name = info.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if (path.is_absolute() or not path.parts or any(p in ("..", ".") or any(c in p for c in ':<>"|?*')
                    or p.endswith((".", " ")) for p in path.parts)):
                raise ValueError("ZIP contains an unsafe filename")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("ZIP symbolic links are not supported")
            if info.flag_bits & 1:
                raise ValueError("Encrypted ZIPs are not supported. Extract them locally first.")
            if info.is_dir() or path.suffix.lower() != ".pdf":
                continue
            if any(p.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)],
                                               *[f"LPT{i}" for i in range(1, 10)]} for p in path.parts):
                raise ValueError("ZIP contains a filename reserved by Windows")
            key = str(path).casefold()
            if key in seen:
                raise ValueError("ZIP contains duplicate PDF paths")
            seen.add(key)
            total_bytes += info.file_size
            if total_bytes > max_bytes:
                raise ValueError("Expanded PDFs exceed the configured ZIP size limit")
            target = destination.joinpath(*path.parts)
            if not target.resolve().is_relative_to(destination):
                raise ValueError("ZIP path escapes the import folder")
            files.append((info, target))
        if not files:
            raise ValueError("ZIP contains no PDFs. Extract nested ZIPs first.")
        if shutil.disk_usage(destination).free < total_bytes + 100 * 1024**2:
            raise ValueError("Not enough disk space to extract this ZIP")
        written = 0
        for index, (info, target) in enumerate(files):
            if cancelled and cancelled():
                raise ImportCancelled("ZIP import cancelled")
            target.parent.mkdir(parents=True, exist_ok=True)
            created = False
            try:
                with target.open("xb") as outgoing:
                    created = True
                    with source.open(info) as incoming:
                        while chunk := incoming.read(1024 * 1024):
                            if cancelled and cancelled():
                                raise ImportCancelled("ZIP import cancelled")
                            written += len(chunk)
                            if written > max_bytes:
                                raise ValueError("Expanded ZIP exceeds the size limit")
                            outgoing.write(chunk)
            except Exception:
                # Only remove a file created by this extraction, never an existing file.
                if created:
                    target.unlink()
                raise
            if progress:
                progress(index + 1, len(files), f"Extracting {info.filename}")
    return [target for _, target in files]


def import_archives(paths, progress=None, cancelled=None):
    """Caller owns TemporaryDirectory until all previews/exports have finished."""
    session = tempfile.TemporaryDirectory(prefix="cert-stamp-import-")
    root = Path(session.name)
    try:
        for index, archive in enumerate(paths):
            # Separate archives cannot collide even when their basenames match.
            folder = root if len(paths) == 1 else root / f"{index + 1:02d}-{Path(archive).stem}"
            extract_pdfs(archive, folder, progress, cancelled)
        return session, root
    except Exception:
        session.cleanup()
        raise


def package_results(output, report, audit, destination=None, progress=None, cancelled=None):
    """Include only this run's successful PDFs and audit, never stale output files."""
    output = Path(output).resolve()
    target = Path(destination) if destination else output.parent / f"{output.name}-{uuid.uuid4().hex[:8]}.zip"
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{uuid.uuid4().hex}.tmp")
    successes = [r for r in report if r["status"] in ("stamped", "signed")]
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for index, row in enumerate(successes):
                if cancelled and cancelled():
                    raise ImportCancelled("ZIP export cancelled; stamped PDFs and report are preserved")
                path = (output / row["file"]).resolve()
                if not path.is_relative_to(output):
                    raise ValueError("Invalid result path")
                archive.write(path, arcname=path.relative_to(output).as_posix())
                if progress:
                    progress(index + 1, len(successes), "Packaging stamped PDFs")
            archive.write(audit, arcname=Path(audit).name)
        os.link(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return target
