# Cert Stamp Pro

A local Python desktop tool with separate modules for batch stamping and visible signature images on certificate PDFs. Choose an extracted folder or import one or more ZIP batches, select your image once, preview placement on any page, then export copies and an optional ZIP with the same filenames and regional subfolders.

## Start on Windows

Install Python 3.11 or newer from python.org, including Tcl/Tk and the Python launcher. Double-click **start.bat**. The first launch installs PyMuPDF and Pillow into this project's `.venv` folder. Internet access is needed for installation; certificate processing stays on your computer and requires no API key.

Or run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Stamp certificates

1. Select the **stamp** module. Browse to the certificate folder, or click **Import ZIP files** and select one or more ZIPs. ZIP batches are extracted and scanned automatically. Regional subfolders are preserved; multiple archives get separate top-level folders to avoid collisions.
2. Choose an output folder and your PNG/JPG stamp. Transparent PNG gives the best result. White-background removal is optional; inspect its preview before exporting.
3. Choose first, last, or all pages and click **Scan folder**.
4. Select a certificate in the list. Use the page buttons to inspect each page. A green rectangle is ready; an amber rectangle needs review. A red occupied area may already contain a stamp and is skipped. Occupied pages show their original content without adding another stamp in preview.
5. If placement needs correction, drag a rectangle over the intended area and click **Approve this area**. Approval applies only to that page of that PDF. Already stamped pages cannot be reapproved.
6. Leave **Also create ZIP** selected if you want a ZIP delivery bundle, then click **Export ready certificates**. PDFs with uncertain or occupied selected pages are skipped in full. A JSON report records each file's result, source/output SHA-256 hashes, placement decisions, and errors. The ZIP includes only this run's successful PDFs and report, not older files already in the output folder. Cancel stops between files, and is also checked while importing ZIP data.

Use **PDF next/previous** and the page controls to preview each certificate. Enable **Require approval for each selected page** when you want every target page inspected before export, then click **Approve this area** on each target page. Pages that were only automatically detected remain excluded until approved when this option is on.

## Batch signature module

1. Select **signature** in the Module field and choose your signature PNG/JPEG. A transparent PNG is preferred. For JPEG signatures, enable white image background removal and inspect the result.
2. Choose the folder/ZIP and output folder. Select first, last, or all target pages.
3. Enter a signatory role such as `Principal`, `Registrar`, or an exact custom label if the certificate has several signature fields. Leave the field empty for automatic matching of common signature labels.
4. Scan the batch. The tool searches for a horizontal vector line, thin rectangle, or text underscore line near the selected label. A clear area immediately above that line is used for the signature, with its proportions preserved.
5. Preview each PDF/page, adjust unclear areas by drawing a rectangle, and approve if required. Unlabelled or ambiguous lines require manual placement. Existing text/ink in the proposed area causes a skip.
6. Click **Export ready certificates** to save signed copies and the optional batch ZIP. The audit records `operation: signature`. Signature markers are separate from stamp markers: an existing stamp elsewhere does not automatically block a clear signature field.

This module applies a visible signature image. It does not create a certificate-backed digital signature, authenticate the signer, or provide cryptographic verification. Previously digitally signed/flagged PDFs remain protected from modification. Signature and stamp images are kept local and are not included in the repository.

To stamp and sign the same certificates, finish one module, then select its exported folder as the next module's input and choose a new output folder. Each pass preserves the earlier overlay and checks its own field.

## Other brands and redesigned certificates

Placement is based on the actual field geometry, not a KNEC logo, year, unit count, or hard-coded coordinates. Common stamp/seal labels are supported. Enter an exact **Field label** to support new wording, such as `Assessment Approval`, then scan again. Changing the module or label clears earlier placement decisions so they cannot be applied to the wrong field.

No automatic detector can guarantee all future certificate designs. Raster-only boxes/lines, unfamiliar layouts, and ambiguous roles need manual placement and preview approval. Every certificate and page is checked independently; one document's coordinates are not reused across the batch.

For already stamped batches, import the ZIP or choose its extracted folder, inspect the results, then click **Save review report**. No stamp image is needed to scan or save a review. Files marked `stamped` were marked by this tool; `occupied` means text, ink, or a possible external stamp was found in the box. This is not an authenticity check.

Automatic placement requires a unique recognized stamp label near a clear vector box, including a dotted box composed of four separate strokes. Labels may be to the left of, above, below, or inside the box. Supported labels include `College Stamp & Date`, `College Stamp`, `Stamp & Date`, and `Official Stamp`. Every page is analyzed independently. Tests cover certificates with one through seven units and deliberately varied box heights: the actual box determines placement, not the unit count, filename, or another page's coordinates.

Scanned PDFs can use optional local Tesseract OCR when its language data is installed. Without OCR or a recognizable vector box, draw a clear area and approve it in preview. Boxes represented as disconnected tiny segments, raster images, and unusual layouts may require manual placement. Existing-stamp detection is conservative: ink can be flagged even when it is not a stamp, and very faint ink may be missed. Preview real certificates before a production batch.

## Large batches and ZIPs

PDFs are inspected and exported one at a time; previews load only the selected PDF. ZIP extraction and packaging use disk storage and streamed file reads, with ZIP64 support. The current import limit is 100,000 entries and 20 GiB of expanded PDF content per archive; sufficient local disk space is also required for extracted input, stamped output, and the ZIP bundle. These limits are safeguards, not a tested capacity guarantee. Nested ZIPs must be extracted separately. ZIP passwords, links, unsafe paths, duplicate PDF paths, and Windows-reserved filenames are rejected. Non-PDF archive entries are not imported.

A synthetic 281-file mixed ZIP batch was tested locally: 252 PDFs were stamped, 28 occupied PDFs were skipped, and one damaged PDF was reported as an error. Import, analysis, export, and packaging took about 10 seconds on the test computer. Real performance depends on page count, PDF size, image resolution, OCR, and disk speed.

A separate 1,000-file synthetic ZIP benchmark with 1-7 units, independently varied box positions, stamp/seal labels and all four rotations exported all 1,000 clear certificates. Every overlay's bounds and original-file hash were verified, along with retained text and page rotations. Import, processing, packaging and verification took 36.59 seconds locally. These were small synthetic PDFs; this is not a timing or correctness guarantee for 1,000 real certificates. Run `python benchmarks/mixed_batch.py --count 1000` to reproduce the checks with fresh synthetic files.

The desktop now shows a preflight summary of ready, review, occupied, already-applied, error and existing-output counts. Read [the batch guide](BATCH_GUIDE.md) for a step-by-step 1,000-file workflow and suggested future improvements.

Extracted ZIP inputs are temporary and cleaned when the source is changed or the app closes normally. Original ZIPs are never modified. Scan cancellation is shown as a partial checked count; rescan to process the full batch.

## Data and file handling

- Originals are never modified. Existing output PDFs are never overwritten.
- Output cannot be the source folder or a parent of it. If output is inside source, it is excluded from subsequent scans.
- Password-protected PDFs and PDFs flagged as digitally signed are rejected.
- Changes to source files after scanning require another scan.
- Text, page count, and page rotations are retained; stamping is a visible image overlay, not a cryptographic signature.
- Export uses atomic hard links to prevent overwrites. Use a local NTFS folder on Windows; destinations without hard-link support will be reported as errors. Copy completed results to a USB drive afterward if needed.
- No certificates, stamp images, reports, or credentials are included in the source repository.

## Try fictitious samples

```powershell
.\.venv\Scripts\python.exe make_demo.py
```

Choose `output/demo/certificates` and `output/demo/test-stamp.png` in the stamp module, or `output/demo/sample-signature.png` in the signature module. Samples include two regional folders, different page placements, a Principal signature line, and a rotated PDF. The stamp and signature are marked as samples.

## Command line

```powershell
.\.venv\Scripts\python.exe cli.py "C:\Certificates" "C:\Stamped" --stamp "C:\Stamp.png" --pages all
.\.venv\Scripts\python.exe cli.py "C:\Certificates.zip" "C:\Stamped" --stamp "C:\Stamp.png" --zip-output
.\.venv\Scripts\python.exe cli.py "C:\Already-stamped.zip" "C:\Review" --review-only
.\.venv\Scripts\python.exe cli.py "C:\Certificates.zip" "C:\Signed" --signature "C:\Signature.jpg" --field-label "Principal" --remove-white --zip-output
.\.venv\Scripts\python.exe cli.py "C:\Certificates" "C:\Review" --module signature --field-label "Registrar" --review-only
```

The command line exports only automatically ready placements. Exit status 2 means some PDFs were skipped or failed; inspect the report and use the desktop preview to review them.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover independent page placement, rotated-page ink checks, output integrity, repeated stamping, changed sources, regional folders, encrypted/corrupt inputs, uncertain placements, cancellation, and white-background removal. Real certificate layouts should be previewed before a production batch.

PyMuPDF is distributed under AGPL/commercial licensing; review its license before distributing this application in a proprietary product.
