"""Build a clean runtime folder/ZIP from an explicit file allowlist."""
import shutil
import zipfile
from pathlib import Path

RUNTIME = ("app.py", "archives.py", "blank_space.py", "cli.py", "email_delivery.py", "email_ui.py",
           "signatures.py", "stamper.py", "start.bat", "requirements.txt")
GUIDES = ("MODULES_AND_EXPORTS.md", "BATCH_GUIDE.md", "EMAIL_GUIDE.md")


def main():
    source = Path(__file__).resolve().parent
    target = source / "Live Stamping"
    if target.is_symlink() or not target.resolve().is_relative_to(source):
        raise ValueError("Release folder must stay inside this workspace")
    target.mkdir(exist_ok=True)
    (target / "guides").mkdir(exist_ok=True)
    files = []
    for name in RUNTIME:
        shutil.copy2(source / name, target / name)
        files.append(target / name)
    shutil.copy2(source / "LIVE_GUIDE.md", target / "README.md")
    files.append(target / "README.md")
    for name in GUIDES:
        text = (source / name).read_text(encoding="utf-8").replace("(README.md)", "(../README.md)")
        (target / "guides" / name).write_text(text, encoding="utf-8")
        files.append(target / "guides" / name)
    archive = source / "stamping-tool-live.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in files:
            zipped.write(path, path.relative_to(source).as_posix())
    print(f"Runtime folder: {target}")
    print(f"Runtime ZIP: {archive} ({len(files)} application/guide files, no sample or development data)")


if __name__ == "__main__":
    main()
