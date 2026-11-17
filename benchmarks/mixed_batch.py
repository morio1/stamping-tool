"""Reproducible synthetic ZIP benchmark. Never uses real student documents."""
import argparse
import json
import sys
import tempfile
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf as fitz
from PIL import Image, ImageDraw
from archives import import_archives, package_results
from stamper import batch_export, batch_preflight, digest, discover, inspect, stamp_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--workdir", type=Path, default=Path("output/benchmarks"))
    args = parser.parse_args()
    if args.count < 1:
        parser.error("Count must be positive")
    args.workdir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="mixed-units-", dir=args.workdir)).resolve()
    source = root / "input"
    for i in range(args.count):
        units = i % 7 + 1
        # Position is deliberately independent of subject count.
        y, x = 240 + (i * 37) % 140, 150 + (i % 3) * 15
        folder = source / f"Region-{i % 12:02}"
        folder.mkdir(parents=True, exist_ok=True)
        with fitz.open() as doc:
            page = doc.new_page(width=842, height=595)
            page.insert_text((60, 50), "SYNTHETIC CERTIFICATE - TEST DATA ONLY", fontsize=16)
            for n in range(units):
                page.insert_text((80, 90 + n * 15), f"9101/{101+n} SAMPLE SUBJECT", fontsize=8)
            label = "Official Seal:" if i % 5 == 0 else "College Stamp & Date:"
            page.insert_text((x - 90, y + 40), label, fontsize=7)
            for a, b in [((x, y), (x+182, y)), ((x, y+73), (x+182, y+73)),
                         ((x, y), (x, y+73)), ((x+182, y), (x+182, y+73))]:
                page.draw_line(a, b, dashes="[.73 1.45] .73", width=.73)
            page.set_rotation((i % 4) * 90)
            doc.save(folder / f"certificate-{i:04}.pdf")
    image = Image.new("RGBA", (400, 140), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rectangle((4, 4, 395, 135), outline="#124bac", width=5)
    pen.text((150, 60), "TEST ONLY", fill="#124bac")
    image.save(root / "test-stamp.png")
    archive = root / "input.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in source.rglob("*.pdf"):
            zipped.write(path, path.relative_to(source).as_posix())
    started = time.perf_counter()
    session, imported = import_archives([archive])
    try:
        certs = [inspect(path) for path in discover(imported)]
        preflight = batch_preflight(certs, imported, root / "stamped")
        assert preflight["ready"] == args.count, preflight
        audit, report = batch_export(certs, imported, root / "stamped", stamp_bytes(root / "test-stamp.png"))
        result = package_results(root / "stamped", report, audit)
        assert len(report) == args.count and all(r["status"] == "stamped" for r in report)
        for cert in certs:
            assert digest(cert.path) == cert.digest
            target = root / "stamped" / cert.path.relative_to(imported)
            with fitz.open(cert.path) as original, fitz.open(target) as stamped:
                assert len(stamped) == len(original)
                assert stamped[0].rotation == original[0].rotation
                assert stamped[0].get_text() == original[0].get_text()
                images = stamped[0].get_image_info()
                assert len(images) == 1
                allowed = fitz.Rect(cert.pages[0].rect) + (-.1, -.1, .1, .1)
                assert allowed.contains(fitz.Rect(images[0]["bbox"]))
        with zipfile.ZipFile(result) as zipped:
            assert len(zipped.namelist()) == args.count + 1 and zipped.testzip() is None
        summary = {"synthetic_certificates": args.count, "units": "1-7", "rotations": [0,90,180,270],
                   "stamped": args.count, "originals_unchanged": True,
                   "all_overlay_bounds_verified": True,
                   "seconds_including_verification": round(time.perf_counter() - started, 2)}
        (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary))
        print(f"Results: {root}")
    finally:
        session.cleanup()


if __name__ == "__main__":
    main()
