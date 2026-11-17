"""Command-line automatic stamping. Uncertain placements are skipped."""
import argparse
import json
import zipfile
from dataclasses import asdict
from pathlib import Path

from stamper import batch_export, discover, inspect, stamp_bytes
from archives import import_archives, package_results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Certificate folder or ZIP archive")
    parser.add_argument("output", type=Path, help="Destination folder")
    parser.add_argument("--stamp", type=Path, help="PNG or JPG stamp (not needed for review-only)")
    parser.add_argument("--pages", choices=("first", "last", "all"), default="first")
    parser.add_argument("--opacity", type=float, default=0.9)
    parser.add_argument("--remove-white", action="store_true")
    parser.add_argument("--ocr", action="store_true", help="Requires local Tesseract language data")
    parser.add_argument("--zip-output", action="store_true", help="Package this batch's results and report into a ZIP")
    parser.add_argument("--review-only", action="store_true", help="Analyze without stamping; save a JSON review report")
    args = parser.parse_args()
    session = None
    try:
        root = args.input
        if args.input.is_file() and args.input.suffix.lower() == ".zip":
            session, root = import_archives([args.input])
        files = discover(root, args.output)
        if not files:
            parser.error("No PDFs found in the selected folder")
        certs = [inspect(path, args.ocr) for path in files]
        if args.review_only:
            args.output.mkdir(parents=True, exist_ok=True)
            from uuid import uuid4
            report = args.output / f"review-{uuid4().hex[:8]}.json"
            report.write_text(json.dumps([{"file": str(c.path.relative_to(root)), "source_sha256": c.digest,
                                          "error": c.error, "pages": [asdict(p) for p in c.pages]}
                                         for c in certs], indent=2), encoding="utf-8")
            print(f"Review report: {report}")
            return 0
        if not args.stamp:
            parser.error("--stamp is required unless --review-only is selected")
        image = stamp_bytes(args.stamp, args.opacity, args.remove_white)
        audit, rows = batch_export(certs, root, args.output, image, args.pages,
                                  lambda i, n, status: print(f"{i}/{n}: {status}"))
        print(f"Audit report: {audit}")
        if args.zip_output:
            print(f"ZIP: {package_results(args.output, rows, audit)}")
        return 0 if all(row["status"] == "stamped" for row in rows) else 2
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    finally:
        if session:
            session.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
