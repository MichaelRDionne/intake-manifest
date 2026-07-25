# intake-manifest

Prove that every file in an archive was accounted for — or fail loudly.

## The problem

A bundle of documents arrives as a zip archive, and something downstream has to
process all of it. The tempting approach is an instruction: "open the archive
and read every file." That instruction is forgettable and, worse, unverifiable
— nothing about it proves the tenth file in a ten-file bundle was ever opened.
A process that handles nine of ten files produces output that looks exactly like
one that handled all ten. When a missed document matters, that gap is the whole
problem, and it is invisible.

## The guarantee

This tool replaces the instruction with a contract. For **every** file entry in
the archive, the manifest carries exactly one record with an explicit status:

- `processed` — the extractor read it.
- `flagged` — enumerated and accounted for, but no extractor was configured for
  its type. Surfaced for review, never dropped.
- `failed` — an extractor was expected to read it and could not.

A file cannot vanish silently. It is either listed as processed or listed with
the reason it was not, and an internal tripwire refuses to emit a manifest whose
record count does not equal the number of file entries in the archive. Under
`--strict`, any file that is not fully processed makes the entire run exit
non-zero — so a gap becomes a loud failure at intake time instead of a surprise
someone finds later.

```
$ python intake_manifest.py examples/sample_bundle.zip
MANIFEST for sample_bundle.zip
  file entries : 4
  records      : 4
  processed    : 3
  flagged      : 1
  failed       : 0

  [processed] cover.txt  (42 bytes)
              sha256=d05328e67a5a852e…  extracted 42 chars of text
  [processed] history/intake_notes.md  (49 bytes)
              sha256=aa526b9de6284cbe…  extracted 49 chars of text
  [processed] labs/results.csv  (56 bytes)
              sha256=3ed81207893bc9f2…  extracted 56 chars of text
  [flagged  ] imaging/scan.png  (16 bytes)
              sha256=02a3e298f1533f62…  no extractor configured for '.png' — flagged for review, not dropped
```

The `.png` had no text extractor, so it is flagged rather than quietly skipped.
Add `--strict` and this same bundle exits `3`.

## A boundary a prompt cannot enforce

`--relocate-to DIR` moves the source archive into an approved directory after
manifesting. A prompt can be told to keep archives in the right place; only code
moves the bytes. Turning a data-location rule into a line of code is the point.

## Usage

```
python intake_manifest.py ARCHIVE.zip [--out DIR] [--strict] [--relocate-to DIR]
```

- `--out DIR` — where to write `MANIFEST.json` and `MANIFEST.txt` (default:
  alongside the archive).
- `--strict` — exit `3` if any file is flagged or failed.
- `--relocate-to DIR` — move the archive into `DIR` after manifesting.

Exit codes: `0` success, `2` archive not found, `3` strict check failed.

## Run it

```bash
python examples/make_sample.py          # build the synthetic sample bundle
python intake_manifest.py examples/sample_bundle.zip
pip install pytest && python -m pytest tests/ -v
```

No dependencies beyond the standard library. Test fixtures are synthetic.

## Scope

This is a **reference implementation of the pattern**, not a production tool.
The default extractor handles text so the accounting guarantee is demonstrable
with the standard library alone; a real deployment replaces `process_member`
with whatever it actually needs — OCR, a PDF parser, a classifier — and keeps
the same contract: one accounted-for record per file, or a loud failure.

I run a private tool built on this pattern in my own clinical work; the public
value is the pattern, so that is what this repo is. It is the first of the three
cases in the essay **[When Not to Use a Model](https://github.com/MichaelRDionne/MichaelRDionne/blob/main/when-not-to-use-a-model.md)**
— on when a deterministic check earns its place over a more capable model.

## License

MIT.
