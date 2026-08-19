#!/usr/bin/env python3
"""Split a merged mp3 into N roughly-equal parts along frame boundaries.

Some books, once re-encoded to a low bitrate, would still be too big for a
single file on GitHub Pages (100 MB/file limit). This cuts the *source* mp3
before re-encoding instead of trying to cut the compressed AAC output later.
The cut lands on a real mp3 frame boundary (reusing the frame parser from
concat_book.py), so each half decodes cleanly on its own — afconvert only
needs to decode the audio, not play it back, so the missing VBR header on
each half doesn't matter.
"""
import sys
import os
import mmap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concat_book import parse_frame_length, id3v2_size  # noqa: E402


def leading_junk_size(mm):
    skip = id3v2_size(mm, 0)
    frame_len = parse_frame_length(mm, skip)
    if frame_len:
        frame = bytes(mm[skip:skip + frame_len])
        if frame[4:44].find(b"Xing") != -1 or \
           frame[4:44].find(b"Info") != -1 or \
           frame[4:44].find(b"VBRI") != -1:
            skip += frame_len
    return skip


def frame_offsets(mm, start):
    offsets = []
    offset = start
    size = len(mm)
    while offset + 4 <= size:
        length = parse_frame_length(mm, offset)
        if not length:
            nxt = mm.find(b"\xff", offset + 1)
            if nxt == -1:
                break
            offset = nxt
            continue
        offsets.append(offset)
        offset += length
    offsets.append(size)
    return offsets


def split(path, out_paths):
    n = len(out_paths)
    with open(path, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            start = leading_junk_size(mm)
            offsets = frame_offsets(mm, start)
            total_frames = len(offsets) - 1
            per_part = total_frames // n
            cuts = [start] + [offsets[per_part * i] for i in range(1, n)] + [len(mm)]
            for i, out_path in enumerate(out_paths):
                with open(out_path, "wb") as out:
                    out.write(mm[cuts[i]:cuts[i + 1]])
        finally:
            mm.close()


if __name__ == "__main__":
    src_path = sys.argv[1]
    outputs = sys.argv[2:]
    split(src_path, outputs)
    for p in outputs:
        print("{}: {} bytes".format(p, os.path.getsize(p)))
