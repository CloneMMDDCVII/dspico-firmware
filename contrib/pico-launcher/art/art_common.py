#!/usr/bin/env python3
"""Shared pieces for the Pico Launcher folder art: BMP writers and the system-folder gear.

Two file formats, both read by hand-written parsers in the launcher that reject anything
they do not expect without telling the user why, so both writers are deliberately strict
about what they emit.

  icon.bmp   32x32, 4bpp, 16-entry palette, pixel data at offset 118 exactly.
             Palette index 0 is the DS sprite transparency index, so it is never drawn
             with.  (arm9/source/romBrowser/FileType/BmpFileIconData.cpp)

  cover.bmp  128x96, 8bpp, 256-entry palette, opaque.  Only the left 106 columns are ever
             seen; the rest is padding, which the stock folderCover.png simply fills with
             its background colour.  (BmpFileCover.cpp, docs/Customization.md)
"""
import struct
from PIL import Image, ImageDraw

ICON_W = ICON_H = 32
ICON_DATA_OFFSET = 118

COVER_W, COVER_H = 128, 96
COVER_VISIBLE_W = 106            # what the launcher actually draws
COVER_DATA_OFFSET = 54 + 256 * 4  # 1078

SS = 4                           # supersampling factor for the covers


# ----------------------------------------------------------------------------- BMP output

def write_icon_bmp(path, img, palette):
    """img: a PIL 'P' image, 32x32, indices 0..15.  palette: 16 (r, g, b) tuples."""
    assert img.size == (ICON_W, ICON_H) and img.mode == "P"
    assert len(palette) == 16
    px = img.load()

    rows = []
    for y in range(ICON_H - 1, -1, -1):                    # bottom-up
        row = bytearray()
        for x in range(0, ICON_W, 2):
            hi, lo = px[x, y] & 0xF, px[x + 1, y] & 0xF
            row.append((hi << 4) | lo)                     # BMP is high-nibble-first
        assert len(row) == 16                              # already 4-byte aligned
        rows.append(bytes(row))
    pixels = b"".join(rows)
    assert len(pixels) == 512

    pal = b"".join(struct.pack("<4B", b, g, r, 0) for (r, g, b) in palette)
    dib = struct.pack("<IiiHHIIiiII", 40, ICON_W, ICON_H, 1, 4, 0,
                      len(pixels), 2835, 2835, 16, 16)
    hdr = struct.pack("<2sIHHI", b"BM", ICON_DATA_OFFSET + len(pixels), 0, 0,
                      ICON_DATA_OFFSET)
    assert len(hdr) + len(dib) + len(pal) == ICON_DATA_OFFSET
    with open(path, "wb") as f:
        f.write(hdr + dib + pal + pixels)


def write_cover_bmp(path, img):
    """img: a PIL 'P' image, 128x96, with a palette of at most 256 entries."""
    assert img.size == (COVER_W, COVER_H) and img.mode == "P"
    px = img.load()

    rows = []
    for y in range(COVER_H - 1, -1, -1):                   # bottom-up
        row = bytes(px[x, y] for x in range(COVER_W))
        assert len(row) % 4 == 0                           # 128 is already aligned
        rows.append(row)
    pixels = b"".join(rows)
    assert len(pixels) == COVER_W * COVER_H

    flat = img.getpalette() or []
    flat = flat + [0] * (768 - len(flat))
    pal = b"".join(struct.pack("<4B", flat[i * 3 + 2], flat[i * 3 + 1], flat[i * 3], 0)
                   for i in range(256))
    dib = struct.pack("<IiiHHIIiiII", 40, COVER_W, COVER_H, 1, 8, 0,
                      len(pixels), 2835, 2835, 256, 256)
    hdr = struct.pack("<2sIHHI", b"BM", COVER_DATA_OFFSET + len(pixels), 0, 0,
                      COVER_DATA_OFFSET)
    assert len(hdr) + len(dib) + len(pal) == COVER_DATA_OFFSET
    with open(path, "wb") as f:
        f.write(hdr + dib + pal + pixels)


# ------------------------------------------------------------------------------- the gear

# The six system folders carry the same gear in the same corner, in the same greys, so it
# reads as a marking rather than as part of the picture.  The alternative — a gear as the
# base shape with each folder's symbol shrunk onto it — was tried and rejected: at 32x32
# it leaves about 14x14 for the part that says which folder this is, and all six end up
# looking alike, which is the opposite of the point.
GEAR_DARK = (26, 28, 32)
GEAR_BODY = (122, 128, 136)
GEAR_LIGHT = (208, 212, 218)

# Reserved palette slots, kept clear of every icon's own colours (none reaches 13).
GEAR_I_DARK, GEAR_I_BODY, GEAR_I_LIGHT = 15, 14, 13


def _gear_points(cx, cy, r_out, r_in, teeth=8, phase=0.0):
    """A cog outline: `teeth` square-ish teeth alternating between r_in and r_out."""
    import math
    pts = []
    steps = teeth * 4
    for i in range(steps):
        a = phase + i * 2 * math.pi / steps
        r = r_out if (i % 4) in (0, 1) else r_in
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def draw_gear(d, cx, cy, r_out, fill, outline, hub_fill, hub_r=None, width=1):
    """Draw the marking gear centred on (cx, cy)."""
    r_in = r_out * 0.72
    d.polygon(_gear_points(cx, cy, r_out, r_in), fill=fill, outline=outline)
    body = r_in * 0.98
    d.ellipse([cx - body, cy - body, cx + body, cy + body], fill=fill, outline=outline)
    hr = hub_r if hub_r is not None else r_out * 0.30
    d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=hub_fill, outline=outline)


def stamp_icon_gear(img, palette):
    """Put the system marking in the bottom-right corner of a 32x32 icon, in place.

    Drawn at 8x and knocked down, because a cog with 1px teeth cannot be drawn directly at
    this size without turning into a smudge.  A pale halo sits under it so the marking
    holds its shape over both the light and the dark icons.
    """
    from PIL import Image as _Image
    pal = list(palette)
    pal[GEAR_I_DARK] = GEAR_DARK
    pal[GEAR_I_BODY] = GEAR_BODY
    pal[GEAR_I_LIGHT] = GEAR_LIGHT
    flat = []
    for rgb in pal:
        flat.extend(rgb)
    img.putpalette(flat + [0] * (768 - len(flat)))

    z = 8
    size = 13                                   # the marking's footprint in icon pixels
    mask = _Image.new("L", (size * z, size * z), 0)
    md = ImageDraw.Draw(mask)
    c = size * z / 2.0
    md.ellipse([c - 6.4 * z, c - 6.4 * z, c + 6.4 * z, c + 6.4 * z], fill=1)   # halo
    draw_gear(md, c, c, 5.3 * z, fill=2, outline=3, hub_fill=3, hub_r=1.5 * z)

    x0, y0 = ICON_W - size, ICON_H - size
    px, mp = img.load(), mask.load()
    lut = {1: GEAR_I_LIGHT, 2: GEAR_I_BODY, 3: GEAR_I_DARK}
    for y in range(size):
        for x in range(size):
            votes = {}
            for sy in range(z):
                for sx in range(z):
                    v = mp[x * z + sx, y * z + sy]
                    votes[v] = votes.get(v, 0) + 1
            v = max(votes, key=votes.get)
            if v:
                px[x0 + x, y0 + y] = lut[v]
    return pal
