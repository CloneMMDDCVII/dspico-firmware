#!/usr/bin/env python3
"""Check the folder art the way the launcher checks it, then draw it the way the DS will.

A BMP the launcher does not like is rejected in silence: BmpFileIconData::Load and
BmpFileCover's constructor just return, and the folder falls back to the generic art with
nothing said to the user.  So header validation is reimplemented here, field for field,
from BmpHeader::Validate plus each loader's own extra conditions.

The second half is the part actually worth having.  It decodes each file back out through
the same transforms the hardware applies -- nibble order, tiling, the vertical flip the
cover BG does with REG_BG3PD_SUB, the 106 pixel window, and 5 bits per channel of colour
-- so the preview is what the screen shows rather than what an image viewer shows.
"""
import struct
import sys
from PIL import Image

OK, BAD = "ok", "BAD"


def u16(d, o):
    return struct.unpack_from("<H", d, o)[0]


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def s32(d, o):
    return struct.unpack_from("<i", d, o)[0]


def validate(d, w, h, bpp):
    """BmpHeader::Validate, field for field."""
    errs = []
    if d[0:2] != b"BM":
        errs.append("no BM signature")
    if u32(d, 0x0E) != 40:
        errs.append("DIB header is %d bytes, must be 40" % u32(d, 0x0E))
    if u32(d, 0x12) != w:
        errs.append("width %d, must be %d" % (u32(d, 0x12), w))
    if abs(s32(d, 0x16)) != h:
        errs.append("height %d, must be +/-%d" % (s32(d, 0x16), h))
    if u16(d, 0x1C) != bpp:
        errs.append("%d bpp, must be %d" % (u16(d, 0x1C), bpp))
    if u32(d, 0x1E) != 0:
        errs.append("compression %d, must be 0" % u32(d, 0x1E))
    clr = u32(d, 0x2E)
    if clr not in (0, 1 << bpp):
        errs.append("biClrUsed %d, must be 0 or %d" % (clr, 1 << bpp))
    return errs


def to555(r, g, b):
    """The DS keeps 5 bits a channel, so show the colours it will actually make."""
    return ((r >> 3) * 255 // 31, (g >> 3) * 255 // 31, (b >> 3) * 255 // 31)


def read_palette(d, n):
    return [to555(d[0x36 + i * 4 + 2], d[0x36 + i * 4 + 1], d[0x36 + i * 4]) for i in range(n)]


def check_icon(path):
    d = open(path, "rb").read()
    errs = validate(d, 32, 32, 4)
    off = u32(d, 0x0A)
    if off < 118:
        errs.append("pixel data at %d, BmpFileIconData rejects anything below 118" % off)
    if len(d) < off + 512:
        errs.append("file holds %d bytes of pixels, needs 512" % (len(d) - off))
    if errs:
        return errs, None

    pal = read_palette(d, 16)
    raw = d[off:off + 512]
    top_down = s32(d, 0x16) < 0

    # BmpFileIconData::Load, including the nibble swap into DS sprite order.
    img = Image.new("RGB", (32, 32))
    px = img.load()
    for y in range(32):
        row = raw[(y if top_down else 31 - y) * 16:][:16]
        for tx in range(4):
            val = int.from_bytes(row[tx * 4:tx * 4 + 4], "little")
            val = ((val >> 4) & 0x0F0F0F0F) | ((val & 0x0F0F0F0F) << 4)
            nib = val.to_bytes(4, "little")
            for i in range(4):
                px[tx * 8 + i * 2, y] = pal[nib[i] & 0xF]
                px[tx * 8 + i * 2 + 1, y] = pal[nib[i] >> 4]
    return [], img


def check_cover(path):
    d = open(path, "rb").read()
    errs = validate(d, 128, 96, 8)
    off = u32(d, 0x0A)
    if len(d) < 0x436:
        errs.append("file is %d bytes; the header and palette read is 1078" % len(d))
    if len(d) < off + 128 * 96:
        errs.append("file holds %d bytes of pixels, needs 12288" % (len(d) - off))
    if s32(d, 0x16) < 0:
        errs.append("stored top-down; the cover BG flips rows itself (REG_BG3PD_SUB = -1),"
                    " so a top-down file comes out upside down")
    if errs:
        return errs, None

    pal = read_palette(d, 256)
    raw = d[off:off + 128 * 96]

    # The cover is copied into VRAM in file order and then drawn by an affine BG with
    # PD = -1 from y = 95, which is what turns the bottom-up rows the right way up.
    img = Image.new("RGB", (106, 96))
    px = img.load()
    for y in range(96):
        row = raw[(95 - y) * 128:][:128]
        for x in range(106):
            px[x, y] = pal[row[x]]
    return [], img


if __name__ == "__main__":
    outdir = sys.argv[1]
    names = ["Games", "Enfance", "EZ5Shell", "_gba", "_nds", "_pico", "ROMDAT", "SAVE"]
    failed = 0
    icons, covers = {}, {}
    for n in names:
        for kind, fn, store in (("icon", check_icon, icons), ("cover", check_cover, covers)):
            errs, img = fn("%s/%s.%s.bmp" % (outdir, n, kind))
            if errs:
                failed += 1
                print("%-8s %-5s %s" % (n, kind, BAD))
                for e in errs:
                    print("             - %s" % e)
            else:
                print("%-8s %-5s %s" % (n, kind, OK))
                store[n] = img

    # One sheet: each folder's cover with its icon shown beside it at the size the browser
    # draws it, and again enlarged so the marking can be seen.
    pad, zoom = 8, 2
    cell_w, cell_h = (106 + 32 * 3 + pad * 3) * 1, 96 + pad
    sheet = Image.new("RGB", (cell_w * 2, cell_h * 4 + pad), (26, 26, 30))
    for i, n in enumerate(names):
        cx = (i % 2) * cell_w + pad
        cy = (i // 2) * cell_h + pad
        if n in covers:
            sheet.paste(covers[n], (cx, cy))
        if n in icons:
            sheet.paste(icons[n], (cx + 106 + pad, cy + 96 - 32 - 2))
            sheet.paste(icons[n].resize((32 * zoom, 32 * zoom), Image.NEAREST),
                        (cx + 106 + pad + 32 + pad, cy + 96 - 64 - 2))
    sheet.save("%s/_set_as_the_DS_draws_it.png" % outdir)
    print("\n%d file(s) rejected" % failed)
    sys.exit(1 if failed else 0)
