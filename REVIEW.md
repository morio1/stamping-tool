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

A real supplied sample was reviewed locally. It already contains a visible stamp. Its label is to the left of a dotted box drawn as four independent stroked paths; the original detector missed this layout. The revised detector finds its box and marks it occupied, preventing automatic double stamping. The student's document and images are excluded from GitHub.

New regression fixtures cover one through seven units, independently varied box positions, occupied boxes, rotations, ZIP import/export, malformed paths, duplicate names, existing-file protection, cancellation, and multi-archive collisions. A synthetic 281-file ZIP batch produced 252 stamped PDFs, 28 skips for occupied boxes, and one corrupt-input error, with no original modifications.

Scanned/raster boxes, disconnected tiny dot segments, and unusual labels can still require manual review. Existing-ink checks do not establish stamp authenticity and cannot guarantee detection of very faint stamps. OCR depends on a separately installed local Tesseract configuration. Export requires a filesystem supporting hard links. Very large real batches have not been benchmarked beyond the synthetic test described above.
