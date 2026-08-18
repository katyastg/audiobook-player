#!/usr/bin/env python3
"""Concatenate numbered mp3 chapter files (001.mp3, 002.mp3, ...) into one
continuous mp3 per book. No re-encoding — real audio frames are copied
byte-for-byte. Two kinds of non-audio junk are stripped from every file so
they don't sit as garbage in the middle of the merged stream:

  1. The ID3v2 tag at the start of each file.
  2. A LAME/Xing/Info "VBR header" frame, if present as the very first audio
     frame. This frame carries metadata (e.g. total frame count, encoder
     delay) that some decoders trust as authoritative for the *whole*
     stream — if left in place on a middle fragment, a decoder can treat it
     as "this is where the real content ends" and silently stop decoding
     partway through the merged file.

The merged output therefore has no VBR header of its own. Run
`add_vbr_header.py` on it afterwards to prepend one that describes the whole
stream — without it browsers cannot work out the duration, `audio.duration`
stays NaN, and seeking (including the random-start button) silently fails.
"""
import sys
import os

MPEG1_BITRATES = [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None]
MPEG2_BITRATES = [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None]
SAMPLE_RATES = {
    3: [44100, 48000, 32000, None],  # MPEG1
    2: [22050, 24000, 16000, None],  # MPEG2
    0: [11025, 12000, 8000, None],   # MPEG2.5
}


def id3v2_size(data, offset):
    if data[offset:offset + 3] != b"ID3":
        return 0
    b = data[offset + 6:offset + 10]
    size = (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]
    return 10 + size


def parse_frame_length(data, offset):
    """Return the byte length of the mp3 frame starting at offset, or None
    if there's no valid frame header there."""
    if offset + 4 > len(data):
        return None
    b0, b1, b2, b3 = data[offset], data[offset + 1], data[offset + 2], data[offset + 3]
    if b0 != 0xFF or (b1 & 0xE0) != 0xE0:
        return None
    version_bits = (b1 >> 3) & 0x03  # 3=MPEG1, 2=MPEG2, 0=MPEG2.5
    layer_bits = (b1 >> 1) & 0x03  # 1=Layer III
    if layer_bits != 0x01:
        return None
    bitrate_index = (b2 >> 4) & 0x0F
    samplerate_index = (b2 >> 2) & 0x03
    padding = (b2 >> 1) & 0x01

    rates = SAMPLE_RATES.get(version_bits)
    if rates is None or samplerate_index == 3:
        return None
    samplerate = rates[samplerate_index]
    if samplerate is None:
        return None

    bitrates = MPEG1_BITRATES if version_bits == 3 else MPEG2_BITRATES
    if bitrate_index == 0 or bitrate_index == 15:
        return None
    bitrate = bitrates[bitrate_index]
    if bitrate is None:
        return None

    multiplier = 144 if version_bits == 3 else 72
    length = (multiplier * bitrate * 1000) // samplerate + padding
    if length < 21:
        return None
    return length


def leading_junk_size(data):
    """Bytes to skip at the start of this file's audio data: an ID3v2 tag
    plus a VBR-header pseudo-frame (Xing/Info/VBRI), if either is present."""
    skip = id3v2_size(data, 0)
    frame_len = parse_frame_length(data, skip)
    if frame_len:
        frame = data[skip:skip + frame_len]
        if frame[4:4 + 40].find(b"Xing") != -1 or \
           frame[4:4 + 40].find(b"Info") != -1 or \
           frame[4:4 + 40].find(b"VBRI") != -1:
            skip += frame_len
    return skip


def concat(book_dir, out_path):
    files = sorted(
        f for f in os.listdir(book_dir) if f.lower().endswith(".mp3")
    )
    if not files:
        raise SystemExit("No mp3 files found in " + book_dir)

    with open(out_path, "wb") as out:
        for name in files:
            path = os.path.join(book_dir, name)
            with open(path, "rb") as f:
                data = f.read()
            skip = leading_junk_size(data)
            out.write(data[skip:])
    return len(files)


if __name__ == "__main__":
    book_dir, out_path = sys.argv[1], sys.argv[2]
    n = concat(book_dir, out_path)
    print("Merged {} files -> {}".format(n, out_path))
