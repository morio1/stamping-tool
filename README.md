# Cert Stamp Pro

A local Python desktop tool for batch stamping certificate PDFs. Choose a folder of unstamped certificates, select your stamp image once, preview placement on any page, then export copies with the same filenames and regional subfolders.

## Start on Windows

Install Python 3.11 or newer from python.org, including Tcl/Tk and the Python launcher. Double-click **start.bat**. The first launch installs PyMuPDF and Pillow into this project's `.venv` folder. Internet access is needed for installation; certificate processing stays on your computer and requires no API key.

Or run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Stamp certificates

1. Browse to the certificate folder. Regional subfolders are included automatically.
2. Choose an output folder and your PNG/JPG stamp. Transparent PNG gives the best result. White-background removal is optional; inspect its preview before exporting.
3. Choose first, last, or all pages and click **Scan folder**.
4. Select a certificate in the list. Use the page buttons to inspect each page. A green rectangle is ready; an amber rectangle needs review. The preview uses the same image insertion as the exported PDF.
5. If placement needs correction, drag a rectangle over the intended area and click **Approve this area**. Approval applies only to that page of that PDF. Already stamped pages cannot be reapproved.
6. Click **Stamp ready certificates**. PDFs with uncertain selected pages are skipped in full. A JSON report records each file's result, source/output SHA-256 hashes, placement decisions, and errors. Cancel stops between files.

Automatic placement requires a unique recognized stamp label near a clear vector box. Supported labels include `College Stamp & Date`, `College Stamp`, `Stamp & Date`, and `Official Stamp`. Every page is analyzed independently. The tool does not infer positions from filenames, subject counts, or another page's coordinates.

Scanned PDFs can use optional local Tesseract OCR when its language data is installed. Without OCR or a recognizable box, draw and approve the area in preview. Dotted boxes represented as many separate line segments and unusual layouts may require manual placement. Detection cannot prove every certificate is unstamped: existing ink is a review signal, and automatic repeat detection identifies stamps applied by this tool.

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

Choose `output/demo/certificates` and `output/demo/test-stamp.png` in the app. Samples include two regional folders, different page placements, and a rotated PDF. The stamp is labelled TEST ONLY.

## Command line

```powershell
.\.venv\Scripts\python.exe cli.py "C:\Certificates" "C:\Stamped" --stamp "C:\Stamp.png" --pages all
```

The command line exports only automatically ready placements. Exit status 2 means some PDFs were skipped or failed; inspect the report and use the desktop preview to review them.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover independent page placement, rotated-page ink checks, output integrity, repeated stamping, changed sources, regional folders, encrypted/corrupt inputs, uncertain placements, cancellation, and white-background removal. Real certificate layouts should be previewed before a production batch.

PyMuPDF is distributed under AGPL/commercial licensing; review its license before distributing this application in a proprietary product.
