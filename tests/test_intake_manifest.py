"""The guarantee under test: every file entry in the archive produces exactly
one manifest record with an explicit status, and --strict refuses when any file
was not fully processed."""

import json
import zipfile
from pathlib import Path

import pytest

import intake_manifest as im


def make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_every_file_gets_exactly_one_record(tmp_path):
    archive = make_zip(tmp_path / "bundle.zip", {
        "note.txt": b"hello",
        "data.csv": b"a,b\n1,2\n",
        "records/summary.md": b"# summary",
        "scan.bin": b"\x00\x01\x02\x03",
    })
    manifest = im.build_manifest(archive)
    assert manifest["file_entry_count"] == 4
    assert manifest["record_count"] == 4
    names = {e["name"] for e in manifest["entries"]}
    assert names == {"note.txt", "data.csv", "records/summary.md", "scan.bin"}


def test_binary_is_flagged_not_dropped(tmp_path):
    archive = make_zip(tmp_path / "b.zip", {"scan.bin": b"\x00\xff\x00"})
    manifest = im.build_manifest(archive)
    assert manifest["counts"]["flagged"] == 1
    assert manifest["fully_accounted"] is False
    entry = manifest["entries"][0]
    assert entry["status"] == "flagged"
    assert "not dropped" in entry["detail"]


def test_all_text_is_fully_accounted(tmp_path):
    archive = make_zip(tmp_path / "t.zip", {
        "a.txt": b"one", "b.md": b"two", "c.json": b"{}",
    })
    manifest = im.build_manifest(archive)
    assert manifest["counts"]["processed"] == 3
    assert manifest["fully_accounted"] is True


def test_bad_utf8_in_text_file_fails_loudly(tmp_path):
    # A .txt whose bytes are not valid UTF-8 is a FAILURE, not a silent skip:
    # the extractor was expected to read it and could not.
    archive = make_zip(tmp_path / "bad.zip", {"note.txt": b"\xff\xfe\x00bad"})
    manifest = im.build_manifest(archive)
    assert manifest["counts"]["failed"] == 1
    assert manifest["entries"][0]["status"] == "failed"


def test_directory_entries_do_not_inflate_the_count(tmp_path):
    archive = tmp_path / "dirs.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("folder/", b"")          # explicit directory entry
        zf.writestr("folder/file.txt", b"x")
    manifest = im.build_manifest(archive)
    assert manifest["file_entry_count"] == 1
    assert manifest["entries"][0]["name"] == "folder/file.txt"


def test_strict_exit_code(tmp_path, capsys):
    archive = make_zip(tmp_path / "s.zip", {"ok.txt": b"fine", "x.bin": b"\x00"})
    assert im.main([str(archive)]) == 0                     # lenient: still 0
    archive2 = make_zip(tmp_path / "s2.zip", {"ok.txt": b"fine", "x.bin": b"\x00"})
    assert im.main([str(archive2), "--strict"]) == 3        # strict: refuses


def test_manifest_files_are_written(tmp_path):
    archive = make_zip(tmp_path / "w.zip", {"a.txt": b"hi"})
    out = tmp_path / "out"
    im.main([str(archive), "--out", str(out)])
    written = json.loads((out / "MANIFEST.json").read_text())
    assert written["record_count"] == 1
    assert (out / "MANIFEST.txt").exists()


def test_relocate_moves_the_archive(tmp_path):
    unsafe = tmp_path / "downloads"
    unsafe.mkdir()
    archive = make_zip(unsafe / "r.zip", {"a.txt": b"hi"})
    approved = tmp_path / "approved"
    im.main([str(archive), "--relocate-to", str(approved)])
    assert not archive.exists()                 # gone from the unsafe dir
    assert (approved / "r.zip").exists()         # code moved the bytes


def test_missing_archive_returns_2(tmp_path):
    assert im.main([str(tmp_path / "nope.zip")]) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
