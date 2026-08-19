#!/usr/bin/env python3
"""Re-encode every merged book to 16 kbps mono HE-AAC for GitHub Pages.

Books whose 16 kbps output would exceed Pages' 100 MB/file limit are split
first (source mp3, frame-aligned) into two halves so each half's .m4a stays
under the limit; the rest stay as a single file. Writes finished .m4a files
into audio/ and a JSON manifest (audio/build_manifest.json) recording each
part's real encoded duration, read afterwards to update books.json.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from split_mp3 import split  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MERGED_DIR = os.path.join(ROOT, "merged_fixed")
AUDIO_DIR = os.path.join(ROOT, "audio")

# book id -> number of parts (2 parts keeps each half under 100 MB at 16 kbps)
PARTS = {
    "book-1": 1,
    "book-2": 1,
    "book-3": 1,
    "book-4": 2,
    "book-5": 2,
    "book-6": 2,
    "book-7": 2,
}

DURATION_RE = re.compile(r"estimated duration:\s*([\d.]+)\s*sec")


def afinfo_duration(path):
    out = subprocess.run(["afinfo", path], capture_output=True, text=True, check=True).stdout
    m = DURATION_RE.search(out)
    if not m:
        raise SystemExit("could not read duration from afinfo for " + path)
    return float(m.group(1))


def encode(src_mp3, dst_m4a):
    subprocess.run(
        ["afconvert", "-f", "m4af", "-d", "aach", "-b", "16000", "--mix", "-c", "1", src_mp3, dst_m4a],
        check=True,
    )


def main():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    manifest = {}

    for book_id, n_parts in PARTS.items():
        src = os.path.join(MERGED_DIR, book_id + ".mp3")
        print("=== {} ({} part{}) ===".format(book_id, n_parts, "s" if n_parts > 1 else ""), flush=True)

        parts = []
        if n_parts == 1:
            dst = os.path.join(AUDIO_DIR, book_id + ".m4a")
            encode(src, dst)
            dur = afinfo_duration(dst)
            size = os.path.getsize(dst)
            print("  {} -> {:.1f}s, {:.1f} MB".format(os.path.basename(dst), dur, size / 1e6), flush=True)
            parts.append({"file": "audio/" + book_id + ".m4a", "durationSeconds": dur})
        else:
            with tempfile.TemporaryDirectory() as tmp:
                split_paths = [os.path.join(tmp, "{}-{}.mp3".format(book_id, i + 1)) for i in range(n_parts)]
                split(src, split_paths)
                for i, split_path in enumerate(split_paths):
                    part_name = "{}-{}.m4a".format(book_id, i + 1)
                    dst = os.path.join(AUDIO_DIR, part_name)
                    encode(split_path, dst)
                    dur = afinfo_duration(dst)
                    size = os.path.getsize(dst)
                    print("  {} -> {:.1f}s, {:.1f} MB".format(part_name, dur, size / 1e6), flush=True)
                    parts.append({"file": "audio/" + part_name, "durationSeconds": dur})

        manifest[book_id] = parts

    manifest_path = os.path.join(AUDIO_DIR, "build_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("Manifest written to " + manifest_path)


if __name__ == "__main__":
    main()
