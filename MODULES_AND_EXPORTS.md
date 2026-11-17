# Modules, batch processing and exported files

Developed and maintained by **[Willy Wanjau (@morio1)](https://github.com/morio1)**.

## Choose the right module

| Module | Image to select | Placement method | When to use it |
| --- | --- | --- | --- |
| `stamp` | Stamp PNG/JPEG | A unique labelled stamp/seal box on each page | Certificates with a printed stamp field, including supported dotted boxes |
| `blank-space` | Stamp PNG/JPEG | A clear region without a required field label | Certificates with no designated stamp field |
| `signature` | Signature PNG/JPEG | A unique signatory label and nearby line | Applying a visible signature above a Principal, Registrar or other role's line |

Every document and selected page is analyzed separately. Unit counts do not determine coordinates. A student's seven subjects can shift a field without affecting another student's placement, because their actual page geometry is checked independently.

## Blank-space stamping: certificates without a stamp field

1. Select `blank-space` under Module, and select your stamp image. The Field label setting is not used in this module.
2. Choose the extracted input folder or import one/more ZIP batches. Choose a fresh output folder.
3. Select the intended pages: first, last, or all. Scan the batch.
4. The detector first tries the lower page corners, then searches other positions from the bottom upward. It uses an area up to 170 x 70 PDF points, reduced for smaller pages, with an 8-point clear buffer and 24-point page margins. The stamp image is fitted proportionally inside that area.
5. Both extracted word positions and the rendered page are checked. Scanned text, images, rules, visible marks, logos and annotations can block a candidate. A region must pass both checks before being marked ready.
6. Preview the result. Aesthetically suitable placement cannot be guaranteed just by detecting empty space: for example, a blank strip may be outside the printed certificate frame. Move it manually if necessary. Enable per-page approval when every result must be inspected.
7. Export ready PDFs and the optional ZIP. If no sufficiently clear area is available, the file goes to review and is not stamped automatically.

This is a separate opt-in mode. The labelled-box stamp module does not silently fall back to random empty space when a box cannot be found. Repeat stamps applied by this tool are detected across both stamp modules. A stamp made by another application elsewhere on the page may not be recognized as a duplicate.

Raster inspection is conservative. Off-white scans, watermarks and busy backgrounds may yield no clear area; very faint content may be missed. Preview remains the final suitability check. No content is erased to make room.

## Signing a batch of 1,000 certificates

1. Select `signature`, then choose your signature image once. Use a transparent PNG where possible. With JPEG, enable **Remove white image background** and inspect the preview.
2. Choose your folder or ZIP batches. Regional subfolders are kept. Choose an output folder such as `Signed Certificates`.
3. Select target pages. For 1,000 single-page PDFs, first is sufficient. For multi-page PDFs, all signs every page only when every selected page has a valid field; an unclear selected page causes the complete PDF to be skipped.
4. If multiple signatories appear, enter the exact intended role in **Field label / signatory role**, such as `Principal` or `Registrar`. The automatic mode never chooses arbitrarily between several roles or lines.
5. Scan. Each PDF is checked independently for the role, its line and clear space above that line. The signature image is fitted proportionally into that area. Existing text/ink or a previous signature marker causes a skip/review result.
6. Check the batch summary, then preview the PDFs. Use next/previous PDF and page controls. If an unfamiliar template needs manual placement, draw a clear rectangle and approve it.
7. For fully automatic export of ready fields, leave the approval checkbox off. To inspect every target page, enable **Require approval for each selected page** and approve them individually. Opening a preview does not approve it.
8. Leave **Also create ZIP** selected, then export. Review every skipped/error result before treating the batch as fully complete.

The signature module inserts a visible image. It does not issue or verify a cryptographic digital signature or establish signer authenticity. Documents already flagged as digitally signed remain protected from modification.

## Exactly what is exported?

| Item | What you receive |
| --- | --- |
| Successful certificate | An individual `.pdf`, with its original filename, regional folder hierarchy, original text, page count and rotations retained |
| Stamp run | The stamp image is embedded in the PDF. The report status is `stamped` |
| Signature run | The signature image is embedded in the PDF. The report status is `signed` |
| Audit | An `audit-<timestamp>-<id>.json` file with each source path, source/output SHA-256 hashes where available, operation, page placements, skips and errors |
| Optional ZIP | A sibling ZIP containing only this run's successful PDFs and its audit report, retaining regional subfolders |
| Review-only report | A JSON analysis report saved using **Save review report**, without modifying certificates |

PDFs remain separate files. They are not converted into JPEGs and are not merged into one large PDF. The ZIP is a delivery bundle around the PDFs; the individual files also remain in the output folder. Original PDFs/ZIPs and uploaded stamp/signature images are not overwritten. Existing output PDFs are never replaced.

Example:

```text
Input/
  Nairobi/Student-A.pdf
  Mombasa/Student-B.pdf

Signed Certificates/
  Nairobi/Student-A.pdf
  Mombasa/Student-B.pdf
  audit-20261117-...json

Signed Certificates-<id>.zip
  Nairobi/Student-A.pdf
  Mombasa/Student-B.pdf
  audit-20261117-...json
```

If all 1,000 source PDFs pass, the output contains 1,000 processed PDFs plus the report. If 20 need review, a successful run may produce 980 PDFs and a report accounting for the other 20. Do not assume ZIP creation means every input was processed. Cancelled batches retain completed PDFs and their report, but do not automatically create the normal final ZIP.

## Stamp and signature on the same 1,000 PDFs

Use two passes:

1. Select `stamp` (or `blank-space`) and export to `Stamped Certificates`.
2. Switch to `signature`, select `Stamped Certificates` as the new input, and export to a fresh `Stamped and Signed Certificates` folder.

The second pass preserves the first overlay. It independently checks the signature area; a stamp elsewhere does not by itself block signing. Reconcile both reports because an input skipped in the first pass is absent from that pass's output. Combined one-pass processing and verified resume are not implemented yet.

## Command-line equivalents

```powershell
# No stamp box: search for clear space
.\.venv\Scripts\python.exe cli.py "C:\Certificates.zip" "C:\Stamped" --module blank-space --stamp "C:\Stamp.jpg" --remove-white --zip-output

# Sign a folder and package the results
.\.venv\Scripts\python.exe cli.py "C:\Certificates" "C:\Signed" --signature "C:\Signature.png" --field-label "Principal" --zip-output

# Review signature fields without applying an image
.\.venv\Scripts\python.exe cli.py "C:\Certificates" "C:\Review" --module signature --field-label "Principal" --review-only
```

See [the mixed-batch guide](BATCH_GUIDE.md) for reconciliation and [the README](README.md) for installation. Test with fictitious or small representative inputs before processing an unfamiliar real template.
