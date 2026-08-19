#!/usr/bin/env python3
"""Rewrite books.json from the encoder's manifest, keeping the titles.

Durations come from the freshly encoded files rather than the old mp3s: the
AAC encoder pads each part slightly, and the seek bar is only accurate if
the app's idea of a book's length matches the files it actually plays.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "audio", "build_manifest.json")
BOOKS_JSON = os.path.join(ROOT, "books.json")


def main():
    with open(MANIFEST) as f:
        manifest = json.load(f)
    with open(BOOKS_JSON) as f:
        titles = {b["id"]: b["title"] for b in json.load(f)}

    books = []
    for book_id in sorted(manifest, key=lambda k: int(k.split("-")[1])):
        parts = [
            {"file": p["file"], "durationSeconds": round(p["durationSeconds"], 3)}
            for p in manifest[book_id]
        ]
        books.append({
            "id": book_id,
            "title": titles[book_id],
            "files": parts,
            "durationSeconds": round(sum(p["durationSeconds"] for p in parts), 3),
        })

    with open(BOOKS_JSON, "w") as f:
        json.dump(books, f, ensure_ascii=False, indent=2)
        f.write("\n")

    for b in books:
        print("{}: {} part(s), {:.1f} h".format(b["id"], len(b["files"]), b["durationSeconds"] / 3600))


if __name__ == "__main__":
    main()
