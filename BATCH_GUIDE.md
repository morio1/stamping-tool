# Processing a mixed batch of 1,000 certificates

## What determines stamp placement

Each PDF and target page is analyzed independently. The detector reads the stamp/seal label and the actual closed box beside it, including supported dotted-line boxes. It checks the interior for existing text and ink, then fits the selected image inside the usable area while preserving proportions.

The number of units does not choose the coordinates. If a one-unit certificate has a higher box and a seven-unit certificate has a lower box, the detected box on each page determines placement. The tool does not copy the first student's placement to everyone else.

Automatic placement is conditional on recognizable geometry and a clear field. A ready result is a heuristic decision, not a guarantee of correctness for every certificate design. Missing/ambiguous labels, unfamiliar boxes, existing ink, protected files and damaged inputs are skipped or reported. Scanned PDFs may need local OCR and manual placement.

## Recommended workflow

1. Keep the original ZIP or folder as a backup. Select the stamp module and your PNG/JPEG image. Transparent PNG is preferred; use white-background removal for a JPEG only after checking the preview.
2. Select the certificate folder or import ZIP files. Choose a fresh output folder and the intended target pages. Use first for single-page certificates; choose all only when every page should receive a stamp.
3. Read the batch summary. It counts complete PDFs, so a file with any unclear selected page is excluded from automatic processing. Existing output filenames are counted separately and never overwritten.
4. Preview examples of every layout and unit count present, including 1 and 7 units, and inspect every item marked for review. Check the stamp remains within the box, without covering the field label, grades or other content.
5. For automatic processing of ready files, leave the per-page approval option off. For strict review of the entire batch, enable **Require approval for each selected page**, inspect every target page and click **Approve this area**. Merely opening the preview does not approve it.
6. Leave **Also create ZIP** selected and export. Input files remain unchanged. Output retains the regional subfolders and filenames. Only successful files from this run enter its ZIP, along with the report.
7. Reconcile the final report: successful files plus skipped files, errors and cancellations should account for the batch. A ZIP can contain fewer PDFs than the input when some need attention; that is not a complete 1,000-file delivery until those cases are resolved.
8. Review skipped/error cases separately. Use a fresh output folder for a corrected run. The current tool refuses existing outputs; it does not automatically verify and resume a previous batch.

The signature module uses the same preview and export workflow, with a unique signatory role and nearby signature line. It applies a visible image, not a cryptographic PDF signature.

## Handling a redesigned certificate

Try the exact new field wording in **Field label**, then scan again. Unknown or raster-only fields can be positioned manually on each affected page. Do not assume an older certificate profile will fit a redesign. Preview a sample from each new layout before processing a full batch.

## Capacity and reproducible validation

PDF content is processed one file at a time; the app keeps analysis records for the batch. ZIP import/export uses streamed disk I/O and ZIP64 support. Available disk space, page count, embedded images and OCR affect speed and capacity.

Run the synthetic 1,000-file benchmark with:

```powershell
.\.venv\Scripts\python.exe benchmarks/mixed_batch.py --count 1000
```

It builds fictitious PDFs with 1-7 subjects, independently varied box positions, different stamp/seal labels and all four rotations. It verifies every output image's bounds, unchanged source hashes, retained text/page rotations and ZIP contents. This validates the tested layouts; it is not proof of every real certificate layout.

## Useful next additions (not implemented)

1. **Filter and retry review cases:** show only unclear, occupied or failed files and export a separate follow-up list.
2. **Saved local profiles:** remember an institution's field label, image and settings without reusing fixed coordinates blindly.
3. **Verified resume:** compare previous source/output hashes and continue only unfinished files after an interruption.
4. **Combined stamp and signature:** preview and apply both fields in one export, with independent checks for each.
5. **Excel-friendly batch report:** CSV summaries by region, result and reason for easy reconciliation.
