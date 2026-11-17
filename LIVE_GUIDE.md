# Cert Stamp Pro — Live Stamping

**Developed and maintained by [Willy Wanjau (@morio1)](https://github.com/morio1).**

This folder contains the runnable application and user guides. It excludes development tests, generated certificates, benchmark data, credentials and Git metadata.

## Start

Install Python 3.11+ with its launcher and Tcl/Tk, then double-click **start.bat**. The first start installs the two required libraries into this folder's `.venv`. Later starts use that local environment. Certificate processing is local; Gmail delivery needs internet access and an eligible Google account.

## Choose a module

- **stamp:** find the labelled stamp box on each certificate.
- **blank-space:** find a clear area when no stamp box is specified. Preview the visual suitability before exporting.
- **signature:** find the intended signatory role and line, then fit a visible signature image above it.
- **Email reviewed certificates:** after PDF export and review, match recipients to final PDFs and send through Gmail using the separate reviewed delivery screen.

Choose a source folder or import ZIP files, select the matching image and a fresh output folder, scan, review the summary and previews, then export. Enable per-page approval when every selected page must be checked. Output is individual PDFs, an audit JSON and an optional batch ZIP. Originals are preserved.

For stamp and signature together, stamp first, then select the stamped output as the signature input and use a fresh final output folder. Email from that final output using its audit. No emails are sent automatically after export.

## Detailed guides

- [Modules and exact exports](guides/MODULES_AND_EXPORTS.md)
- [Mixed batches of 1,000 certificates](guides/BATCH_GUIDE.md)
- [Gmail setup, recipient mapping and delivery review](guides/EMAIL_GUIDE.md)

Signatures are visible image overlays, not cryptographic digital signatures. Unknown layouts, busy backgrounds and ambiguous fields may need manual placement. Gmail limits are separate from PDF-processing capacity.
