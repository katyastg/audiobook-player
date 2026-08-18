#!/usr/bin/env python3
"""Prepend a stream-level Xing/Info VBR header frame to a merged mp3.

`concat_book.py` strips the per-fragment Xing/Info headers (each one only
describes its own small fragment, and a decoder that trusts it stops early).
That leaves the merged file with no header at all, which is fine for
straight playback but breaks *seeking*: with no frame count the browser
cannot work out the duration, so `audio.duration` stays NaN and jumping to
an arbitrary position — e.g. the random-start button — silently does
nothing.

This adds a single correct header describing the whole merged stream, so
duration is known up front and seeking maps cleanly onto byte offsets.
"""
import os
import sys
import mmap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concat_book import parse_frame_length, id3v2_size  # noqa: E402

XING_FLAG_FRAMES = 0x0001
XING_FLAG_BYTES = 0x0002
XING_FLAG_TOC = 0x0004


def side_info_size(header_bytes):
    """Bytes of side information between the frame header and the tag body —
    depends on MPEG version and whether the stream is mono."""
    version_bits = (header_bytes[1] >> 3) & 0x03  # 3 = MPEG1
    channel_mode = (header_bytes[3] >> 6) & 0x03  # 3 = mono
    if version_bits == 3:  # MPEG1
        return 17 if channel_mode == 3 else 32
    return 9 if channel_mode == 3 else 17  # MPEG2 / MPEG2.5


def count_frames(mm, start):
    """Walk the frame chain and return (frame_count, first_header_bytes)."""
    first_header = bytes(mm[start:start + 4])
    count = 0
    offset = start
    size = len(mm)
    while offset + 4 <= size:
        length = parse_frame_length(mm, offset)
        if not length:
            # Resync: scan forward for the next plausible frame header.
            nxt = mm.find(b"\xff", offset + 1)
            if nxt == -1:
                break
            offset = nxt
            continue
        count += 1
        offset += length
    return count, first_header


def build_header_frame(first_header, frame_count, total_bytes):
    header = bytearray(first_header)
    header[2] &= ~0x02  # clear the padding bit for a predictable frame size
    frame_len = parse_frame_length(bytes(header) + b"\x00" * 4, 0)
    if not frame_len:
        raise SystemExit("could not size the header frame")

    body = bytearray(frame_len)
    body[0:4] = header

    pos = 4 + side_info_size(header)
    # "Info" is the conventional magic for constant-bitrate streams; it is
    # structurally identical to "Xing".
    body[pos:pos + 4] = b"Info"
    pos += 4
    flags = XING_FLAG_FRAMES | XING_FLAG_BYTES | XING_FLAG_TOC
    body[pos:pos + 4] = flags.to_bytes(4, "big")
    pos += 4
    body[pos:pos + 4] = frame_count.to_bytes(4, "big")
    pos += 4
    body[pos:pos + 4] = total_bytes.to_bytes(4, "big")
    pos += 4
    for i in range(100):
        body[pos + i] = min(255, (255 * i) // 100)
    return bytes(body)


def add_header(path, out_path):
    with open(path, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            start = id3v2_size(mm, 0)
            frame_count, first_header = count_frames(mm, start)
            if not frame_count:
                raise SystemExit("no mp3 frames found in " + path)

            header_frame = build_header_frame(
                first_header, frame_count, len(mm) - start + 0
            )
            # total_bytes must include the header frame itself
            header_frame = build_header_frame(
                first_header, frame_count, len(mm) - start + len(header_frame)
            )

            with open(out_path, "wb") as out:
                out.write(header_frame)
                chunk = 8 * 1024 * 1024
                pos = start
                while pos < len(mm):
                    out.write(mm[pos:pos + chunk])
                    pos += chunk
        finally:
            mm.close()
    return frame_count


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    n = add_header(src, dst)
    print("{}: {} frames -> {}".format(os.path.basename(src), n, dst))
