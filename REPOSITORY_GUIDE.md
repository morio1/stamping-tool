# Repository structure and responsibilities

**Developed and maintained by [Willy Wanjau (@morio1)](https://github.com/morio1).**

## For everyday use

Use the clean **Live Stamping** folder or `stamping-tool-live.zip` produced by `python build_release.py`. Double-click its `start.bat`. It contains only the runtime files and user guides listed explicitly by the builder. It does not copy tests, samples, benchmark output, account credentials, recipient mappings or delivery journals.

The source repository keeps development files so future changes remain testable. They are not required inside the runtime folder. Generated data is ignored by Git. `stamping-tool.zip` is a source snapshot for development; `stamping-tool-live.zip` is the smaller operational package.

## Runtime files

| File | Responsibility |
| --- | --- |
| `start.bat` | Windows launcher: create a local environment when needed, install missing requirements, and start the desktop UI |
| `requirements.txt` | PyMuPDF and Pillow dependency ranges |
| `app.py` | Main desktop workflow: folder/ZIP input, module selection, previews, manual placement, approval, preflight totals and PDF/ZIP export |
| `stamper.py` | Shared certificate analysis, stamp-box recognition, occupancy checks, source hashes, protected-input checks, per-page image insertion and auditable export |
| `blank_space.py` | Opt-in clear-region detection without a stamp label; checks word boxes and rendered marks with a clearance buffer |
| `signatures.py` | Match a unique signatory label to a nearby line and check the signature area; separate repeat-signature tracking |
| `archives.py` | Streaming ZIP import/export, bounded extraction, unsafe-path protection, multi-archive separation and current-run-only packaging |
| `email_delivery.py` | Gmail SMTP delivery logic, reviewed recipient/PDF mappings, audit-hash checks, message generation and durable duplicate/uncertainty tracking |
| `email_ui.py` | Separate Gmail workspace: CSV creation/loading, message and attachment previews, sender credentials in memory, explicit reviewed send and stop controls |
| `cli.py` | Command-line alternative for all placement modules and review-only runs; it does not send email |

## Documentation

| File | Read it for |
| --- | --- |
| `README.md` | Installation, overview and common commands |
| `LIVE_GUIDE.md` | The runtime package's start page, copied as its README |
| `MODULES_AND_EXPORTS.md` | Each placement module, 1,000-file signing workflow, output PDF/ZIP structure and two-pass stamp/sign processing |
| `BATCH_GUIDE.md` | Mixed unit counts, batch preflight, review, reconciliation and capacity limits |
| `EMAIL_GUIDE.md` | Gmail setup, recipient CSV, exact attachments, quotas, journal outcomes and safe recovery from uncertain sends |
| `REVIEW.md` | Design review, validation history and known limits |
| `AUTHORS.md` | Developer attribution, linked to the GitHub account |

## Development and verification

- `tests/` contains regression and desktop integration checks. Mail tests use a fake SMTP service and never send real messages.
- `benchmarks/mixed_batch.py` creates fictitious input batches and verifies PDF overlays, unchanged originals, retained text/rotations and ZIP contents. Use `--module stamp`, `--module signature`, or `--module blank-space`.
- `make_demo.py` creates fictitious samples and TEST ONLY images for trying the app.
- `build_release.py` uses an explicit allowlist to assemble the operational folder/ZIP without private or development data.
- `.github/workflows/tests.yml` runs the checks on Windows with Python 3.11 and 3.14.
- `.gitignore` excludes virtual environments, generated output, imported references, ZIP packages and local delivery files.

## Local-only folders

`.venv/` is the local Python environment. `output/` contains generated demo/benchmark results. `tmp/` contains working diagnostics. `reference/` contains the originally supplied app reference. None is included in the runtime ZIP or committed to GitHub. User-generated runtime output should be stored in a chosen output folder, not mixed into application code.

## Typical end-to-end sequence

1. Import folders/ZIPs and choose the placement module.
2. Analyze each selected page, inspect preflight totals and review previews.
3. Export successful individual PDFs plus audit JSON and optional ZIP.
4. If needed, run the other placement module against that output using a new destination.
5. Review final PDFs and reconcile skips/errors.
6. Open Gmail delivery, map final successful PDFs to recipient addresses, review messages/attachments and explicitly send within the account's quota.

Developer attribution is displayed in the app/docs, not printed onto official certificates. Placement and signature checks are heuristics; they do not certify authenticity or replace operator review. SMTP acceptance is not proof of inbox delivery.
