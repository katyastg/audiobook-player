#!/usr/bin/env python3
"""Turn an ink-on-white drawing into a transparent, tinted PNG.

The ornament sheet comes back from the image generator as black lines on a
solid white page. Laying that over the parchment needs the white gone. CSS
`mix-blend-mode: multiply` does that on desktop but not in iOS Safari — the
page background is painted on the canvas rather than on an element there, so
there is nothing for the ornament to blend against and the white shows as
a box. Baking real transparency into the file removes the guesswork.

Alpha comes from how dark each pixel is (white -> invisible, black -> solid)
and the colour is replaced with a single ink tone, so the lines match the
rest of the page instead of being flatly black.

Pure stdlib: no Pillow on this machine, so the PNG is decoded and re-encoded
by hand. Handles 8-bit greyscale/RGB/RGBA, non-interlaced — which is what
the generator produces.
"""
import struct
import sys
import zlib

INK = (61, 42, 23)  # --ink from style.css


def read_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(path + " is not a PNG")

    pos = 8
    idat = bytearray()
    width = height = depth = color = interlace = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length  # length + type + body + crc

        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break

    if depth != 8 or interlace != 0 or color not in (0, 2, 6):
        raise SystemExit("unsupported PNG: depth={} color={} interlace={}".format(depth, color, interlace))

    channels = {0: 1, 2: 3, 6: 4}[color]
    raw = zlib.decompress(bytes(idat))
    return width, height, channels, unfilter(raw, width, height, channels)


def unfilter(raw, width, height, channels):
    """Undo the per-scanline filters PNG applies before compression."""
    stride = width * channels
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride

        if ftype == 1:  # Sub
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif ftype != 0:
            raise SystemExit("bad filter type " + str(ftype))

        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def write_rgba(path, width, height, pixels):
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)  # filter: none
        raw += pixels[y * stride:(y + 1) * stride]

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def main(src, dst):
    width, height, channels, pixels = read_png(src)
    out = bytearray(width * height * 4)

    for i in range(width * height):
        base = i * channels
        if channels == 1:
            lum = pixels[base]
        else:
            lum = (299 * pixels[base] + 587 * pixels[base + 1] + 114 * pixels[base + 2]) // 1000

        o = i * 4
        out[o] = INK[0]
        out[o + 1] = INK[1]
        out[o + 2] = INK[2]
        out[o + 3] = 255 - lum

    write_rgba(dst, width, height, out)
    print("{} -> {} ({}x{})".format(src, dst, width, height))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
