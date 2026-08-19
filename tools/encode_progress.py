#!/usr/bin/env python3
"""Report how far the build_audio.py encode job has got, as a percentage.

Progress is measured in *audio hours encoded*, not files finished, so a book
that is 12 hours long counts for more than one that is 10. The file being
written right now is counted too: at a fixed 16 kbps its size maps straight
back to seconds of audio (16000 bits/s = 2000 bytes/s), which is accurate
enough for a progress readout.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT, "audio")
BOOKS_JSON = os.path.join(ROOT, "books.json")
BYTES_PER_SECOND = 2000  # 16 kbps
DURATION_RE = re.compile(r"estimated duration:\s*([\d.]+)\s*sec")


def afinfo_duration(path):
    try:
        out = subprocess.run(
            ["afinfo", path], capture_output=True, text=True, check=True
        ).stdout
    except subprocess.CalledProcessError:
        return None
    m = DURATION_RE.search(out)
    return float(m.group(1)) if m else None


def main():
    with open(BOOKS_JSON) as f:
        total = sum(b["durationSeconds"] for b in json.load(f))

    if not os.path.isdir(AUDIO_DIR):
        print("0.0% — encoding has not started")
        return

    files = sorted(f for f in os.listdir(AUDIO_DIR) if f.endswith(".m4a"))
    if not files:
        print("0.0% — encoding has not started")
        return

    # The most recently modified file is the one still being written.
    in_progress = max(files, key=lambda f: os.path.getmtime(os.path.join(AUDIO_DIR, f)))

    done = 0.0
    for name in files:
        path = os.path.join(AUDIO_DIR, name)
        if name == in_progress:
            done += os.path.getsize(path) / BYTES_PER_SECOND
        else:
            done += afinfo_duration(path) or (os.path.getsize(path) / BYTES_PER_SECOND)

    pct = min(100.0, 100.0 * done / total)
    filled = int(round(pct / 2))
    print("[{}{}] {:.1f}%".format("█" * filled, "·" * (50 - filled), pct))
    print("{:.1f} ч из {:.1f} ч".format(done / 3600, total / 3600))
    print("готово:   {}".format(", ".join(f for f in files if f != in_progress) or "—"))
    print("кодирую:  {}".format(in_progress))


if __name__ == "__main__":
    main()
