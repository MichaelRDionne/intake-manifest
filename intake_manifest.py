"""intake-manifest — prove every file in an archive was accounted for.

The guarantee: for every entry in the archive, the manifest carries exactly one
record with an explicit status. A file cannot be silently dropped — it is either
listed as processed, or listed with the reason it was not. Under --strict, any
entry that is not fully processed makes the whole run fail loudly with a
non-zero exit code, instead of passing and leaving a gap for someone to find later.

This is a reference implementation of the pattern. A real deployment plugs a
real extractor (OCR, a parser, a classifier) into `process_member`; here the
default extractor handles text so the guarantee is demonstrable with the
standard library alone and synthetic fixtures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

# Extensions the default reference extractor can read as text. A real deployment
# replaces this whole function; the point being demonstrated is the accounting
# guarantee, not the extractor.
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log", ".xml", ".yaml", ".yml"}

STATUS_PROCESSED = "processed"
STATUS_FLAGGED = "flagged"   # enumerated and accounted for, but not fully extracted
STATUS_FAILED = "failed"     # extractor raised on content it was expected to read


@dataclass
class Entry:
    name: str
    size: int
    sha256: str
    status: str
    detail: str


def process_member(name: str, data: bytes) -> Entry:
    """Produce exactly one Entry for one archive member.

    Contract: this function returns for every input, never raises past the
    caller. Anything it cannot fully handle comes back as FLAGGED or FAILED with
    a reason — never dropped.
    """
    digest = hashlib.sha256(data).hexdigest()
    suffix = Path(name).suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            return Entry(name, len(data), digest, STATUS_FAILED,
                         f"expected text ({suffix}) but decode failed: {exc}")
        return Entry(name, len(data), digest, STATUS_PROCESSED,
                     f"extracted {len(text)} chars of text")

    return Entry(name, len(data), digest, STATUS_FLAGGED,
                 f"no extractor configured for '{suffix or 'no-extension'}' — "
                 f"flagged for review, not dropped")


def build_manifest(archive_path: Path) -> dict:
    """Open the archive, account for every file entry, return the manifest dict.

    Raises RuntimeError if the produced record count does not equal the number
    of file entries enumerated — the internal check that the accounting is total.
    """
    entries: list[Entry] = []
    with zipfile.ZipFile(archive_path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        for info in infos:
            data = zf.read(info.filename)
            entries.append(process_member(info.filename, data))

    if len(entries) != len(infos):
        # Unreachable in normal operation — this is the tripwire that guarantees
        # the loop above produced one record per file entry, no more, no fewer.
        raise RuntimeError(
            f"accounting failure: {len(infos)} file entries but "
            f"{len(entries)} manifest records")

    counts = {
        STATUS_PROCESSED: sum(e.status == STATUS_PROCESSED for e in entries),
        STATUS_FLAGGED: sum(e.status == STATUS_FLAGGED for e in entries),
        STATUS_FAILED: sum(e.status == STATUS_FAILED for e in entries),
    }
    return {
        "archive": archive_path.name,
        "file_entry_count": len(infos),
        "record_count": len(entries),
        "counts": counts,
        "fully_accounted": counts[STATUS_FLAGGED] == 0 and counts[STATUS_FAILED] == 0,
        "entries": [asdict(e) for e in entries],
    }


def render_text(manifest: dict) -> str:
    lines = [
        f"MANIFEST for {manifest['archive']}",
        f"  file entries : {manifest['file_entry_count']}",
        f"  records      : {manifest['record_count']}",
        f"  processed    : {manifest['counts'][STATUS_PROCESSED]}",
        f"  flagged      : {manifest['counts'][STATUS_FLAGGED]}",
        f"  failed       : {manifest['counts'][STATUS_FAILED]}",
        "",
    ]
    for e in manifest["entries"]:
        lines.append(f"  [{e['status']:9}] {e['name']}  ({e['size']} bytes)")
        lines.append(f"              sha256={e['sha256'][:16]}…  {e['detail']}")
    return "\n".join(lines) + "\n"


def relocate(archive_path: Path, dest_dir: Path) -> Path:
    """Move the source archive off wherever it landed and into an approved dir.

    A prompt can be told to keep archives in the right place; only code moves the
    bytes. Returns the new path.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / archive_path.name
    shutil.move(str(archive_path), str(target))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("archive", type=Path, help="path to the .zip archive")
    parser.add_argument("--out", type=Path, default=None,
                        help="directory to write MANIFEST.json / MANIFEST.txt "
                             "(default: alongside the archive)")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero if any file is flagged or failed")
    parser.add_argument("--relocate-to", type=Path, default=None,
                        help="move the archive into this approved directory "
                             "after manifesting")
    args = parser.parse_args(argv)

    if not args.archive.is_file():
        print(f"error: no such archive: {args.archive}", file=sys.stderr)
        return 2

    manifest = build_manifest(args.archive)

    out_dir = args.out or args.archive.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    (out_dir / "MANIFEST.txt").write_text(render_text(manifest))

    print(render_text(manifest), end="")

    if args.relocate_to is not None:
        moved = relocate(args.archive, args.relocate_to)
        print(f"archive relocated to {moved}")

    if args.strict and not manifest["fully_accounted"]:
        print("STRICT: archive not fully processed — see flagged/failed entries "
              "above.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
