"""Command-line automatic stamping. Uncertain placements are skipped."""
import argparse
from pathlib import Path

from stamper import batch_export, discover, inspect, stamp_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Unstamped certificate folder")
    parser.add_argument("output", type=Path, help="Destination folder")
    parser.add_argument("--stamp", type=Path, required=True, help="PNG or JPG stamp")
    parser.add_argument("--pages", choices=("first", "last", "all"), default="first")
    parser.add_argument("--opacity", type=float, default=0.9)
    parser.add_argument("--remove-white", action="store_true")
    parser.add_argument("--ocr", action="store_true", help="Requires local Tesseract language data")
    args = parser.parse_args()
    try:
        image = stamp_bytes(args.stamp, args.opacity, args.remove_white)
        files = discover(args.input, args.output)
        if not files:
            parser.error("No PDFs found in the selected folder")
        certs = [inspect(path, args.ocr) for path in files]
        audit, rows = batch_export(certs, args.input, args.output, image, args.pages,
                                  lambda i, n, status: print(f"{i}/{n}: {status}"))
        print(f"Audit report: {audit}")
        return 0 if all(row["status"] == "stamped" for row in rows) else 2
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
