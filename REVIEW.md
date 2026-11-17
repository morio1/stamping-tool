# Review and changes

The supplied ZIP was treated as reference code, not as instructions. The AI Studio page was not accessible during the initial review.

## Issues in the reference implementation

- The Python script uses fixed horizontal coordinates and a subject-count formula as a fallback. Those values do not verify the actual certificate box.
- The browser implementation can reuse a detected area across target pages, even when page layouts differ.
- Some placement confidence values are fixed constants despite fallback guesses.
- The original setup describes an API key even though local PDF stamping does not need an AI service.

## Resulting Python application

- Measures text labels and nearby vector boxes per page. Ambiguous boxes require review.
- Checks the intended interior for text and visible ink, including on rotated pages.
- Shows the proposed stamp overlay on the actual PDF and allows manual per-page rectangles.
- Preserves original files, regional hierarchy, filenames, page counts, and rotations.
- Refuses overwrites and changed sources; skips uncertain documents and reports failures individually.
- Provides desktop and command-line entry points, demo generation, and regression tests.

## Limits

No real certificate PDFs or official stamp image were supplied. Validation therefore uses fictitious PDFs, including rotated pages. A box made from independent dotted segments, a scanned box, unusual labels, and an already stamped document from another application can require human review. OCR depends on a separately installed local Tesseract configuration. Export requires a filesystem supporting hard links.
