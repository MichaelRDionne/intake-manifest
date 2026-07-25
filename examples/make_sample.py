"""Build examples/sample_bundle.zip from synthetic files, then run the manifest.

All content here is invented for demonstration. Run from the repo root:
    python examples/make_sample.py
"""
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE / "sample_bundle.zip"

# A synthetic "records bundle": a few readable documents and one binary that the
# default text extractor cannot read — so the manifest shows the flagged path.
MEMBERS = {
    "cover.txt": b"Records bundle 42 - 4 documents enclosed.\n",
    "history/intake_notes.md": b"# Intake notes\n\nSynthetic example. No real data.\n",
    "labs/results.csv": b"panel,value,unit\nsodium,140,mmol/L\npotassium,4.1,mmol/L\n",
    "imaging/scan.png": bytes.fromhex("89504e470d0a1a0a0000000d49484452"),  # PNG header only
}


def main() -> None:
    with zipfile.ZipFile(BUNDLE, "w") as zf:
        for name, data in MEMBERS.items():
            zf.writestr(name, data)
    print(f"wrote {BUNDLE.relative_to(HERE.parent)} with {len(MEMBERS)} files")


if __name__ == "__main__":
    main()
