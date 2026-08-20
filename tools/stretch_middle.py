#!/usr/bin/env python3
"""Make the map sheet taller without distorting the crest or the ribbon.

The artwork is drawn 2:3, but a modern phone screen is closer to 1:2. The
page stretches the picture to fill the screen, which stretches the crest and
the ribbon with it — and those are the parts with lettering, where stretching
shows. Here the two ends are copied at their original height and only the
blank middle is stretched, so the extra height lands on plain parchment.

Rows are blended rather than duplicated, so the added height does not band.

Pure stdlib PNG handling is reused from ink_to_alpha.py: there is no Pillow
on this machine.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ink_to_alpha import read_png, write_rgba  # noqa: E402

KEEP_TOP = 400      # crest and everything above it
KEEP_BOTTOM = 1150  # ribbon and everything below it


def main(src, dst, target_height):
    width, height, channels, px = read_png(src)
    if channels < 3:
        raise SystemExit("expected a colour image")

    def row(y):
        """One source row as a list of RGB triples."""
        base = y * width * channels
        return [px[base + i * channels:base + i * channels + 3] for i in range(width)]

    middle_src = KEEP_BOTTOM - KEEP_TOP
    middle_dst = target_height - KEEP_TOP - (height - KEEP_BOTTOM)
    if middle_dst < middle_src:
        raise SystemExit("target height is shorter than the artwork's fixed ends")

    out = bytearray(width * target_height * 4)

    def put(dest_y, pixels):
        o = dest_y * width * 4
        for x in range(width):
            r, g, b = pixels[x]
            out[o] = r; out[o + 1] = g; out[o + 2] = b; out[o + 3] = 255
            o += 4

    for y in range(KEEP_TOP):
        put(y, row(y))

    for i in range(middle_dst):
        # position in the source middle, blended between the two nearest rows
        pos = KEEP_TOP + i * (middle_src - 1) / (middle_dst - 1)
        y0 = int(pos)
        y1 = min(y0 + 1, KEEP_BOTTOM - 1)
        t = pos - y0
        a, b = row(y0), row(y1)
        put(KEEP_TOP + i,
            [(int(a[x][0] + (b[x][0] - a[x][0]) * t),
              int(a[x][1] + (b[x][1] - a[x][1]) * t),
              int(a[x][2] + (b[x][2] - a[x][2]) * t)) for x in range(width)])

    for i, y in enumerate(range(KEEP_BOTTOM, height)):
        put(KEEP_TOP + middle_dst + i, row(y))

    write_rgba(dst, width, target_height, out)

    print("{} ({}x{}) -> {} ({}x{})".format(src, width, height, dst, width, target_height))
    print("crest ends at {:.1f}%, ribbon starts at {:.1f}% of the new height".format(
        KEEP_TOP / target_height * 100,
        (KEEP_TOP + middle_dst) / target_height * 100))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
