#!/usr/bin/env python3
"""Draw the 128x96 8bpp folder covers for Pico Launcher and write them as cover.bmp.

A cover is the large preview on the top screen for whatever is selected in the browser
(RomBrowserTopScreenView.cpp), or the carousel tile itself in the CoverFlow layout.  Only
the left 106 columns are drawn; the remaining 22 are padding, which the stock
folderCover.png simply fills with its background.

Unlike the icons these are not hand-placed pixels.  There is room here for real shapes and
256 colours to render them in, so each subject is drawn at 4x in RGB and knocked down,
which is what makes the curves and the shading possible at all.  The subjects match the
icons deliberately: the same folder should look like the same thing on both screens.
"""
import sys
from PIL import Image, ImageDraw

from art_common import (COVER_W, COVER_H, COVER_VISIBLE_W, SS, write_cover_bmp,
                        draw_gear, GEAR_DARK, GEAR_BODY, GEAR_LIGHT)

CX = COVER_VISIBLE_W / 2.0          # 53: the centre of what is actually seen
CY = COVER_H / 2.0                  # 48

COVERS = {}


def cover(name, system, bg):
    def deco(fn):
        COVERS[name] = (fn, system, bg)
        return fn
    return deco


def _gradient(top, bottom):
    """A soft vertical wash.  Flat fields band badly once the DS drops to 5 bits a
    channel; a gradient gives the quantiser something to work with and looks less bare."""
    img = Image.new("RGB", (COVER_W * SS, COVER_H * SS))
    d = ImageDraw.Draw(img)
    h = COVER_H * SS
    for y in range(h):
        t = y / (h - 1)
        d.line([0, y, COVER_W * SS, y],
               fill=tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img


def rr(d, box, radius, **kw):
    d.rounded_rectangle([v * SS for v in box], radius=radius * SS, **kw)


def rect(d, box, **kw):
    d.rectangle([v * SS for v in box], **kw)


def ell(d, box, **kw):
    d.ellipse([v * SS for v in box], **kw)


def poly(d, pts, **kw):
    d.polygon([(x * SS, y * SS) for x, y in pts], **kw)


def line(d, pts, width=1, **kw):
    d.line([(x * SS, y * SS) for x, y in pts], width=round(width * SS), **kw)


# --------------------------------------------------------------------------------- subjects

@cover("SAVE", system=True, bg=((214, 240, 241), (150, 205, 210)))
def save_cover(d):
    body, edge = (58, 176, 184), (18, 62, 66)
    rr(d, [CX - 27, CY - 27, CX + 27, CY + 27], 3, fill=body, outline=edge, width=1)
    rect(d, [CX - 25, CY - 25, CX + 25, CY - 6], fill=(38, 132, 138))
    rect(d, [CX - 14, CY - 27, CX + 12, CY - 6], fill=(216, 226, 228), outline=edge)
    rect(d, [CX + 1, CY - 25, CX + 10, CY - 8], fill=(126, 140, 143))       # slider
    rect(d, [CX - 11, CY - 23, CX - 3, CY - 9], fill=(24, 80, 84))          # cut-out
    rect(d, [CX - 19, CY - 2, CX + 19, CY + 25], fill=(244, 248, 248), outline=edge)
    for i, y in enumerate((5, 11, 17)):
        line(d, [(CX - 15, CY + y), (CX + 15 - i * 8, CY + y)],
             width=2, fill=(158, 172, 175))


@cover("ROMDAT", system=True, bg=((252, 240, 210), (228, 196, 140)))
def romdat_cover(d):
    edge, top, side, hi = (96, 62, 8), (248, 206, 108), (214, 154, 34), (255, 240, 200)
    for i, cy in enumerate((CY + 16, CY + 1, CY - 14)):
        rect(d, [CX - 26, cy - 5, CX + 26, cy + 5], fill=side, outline=None)
        ell(d, [CX - 26, cy + 1, CX + 26, cy + 11], fill=side, outline=edge)
        rect(d, [CX - 26, cy - 5, CX + 26, cy + 6], fill=side)
        line(d, [(CX - 26, cy - 5), (CX - 26, cy + 6)], fill=edge)
        line(d, [(CX + 26, cy - 5), (CX + 26, cy + 6)], fill=edge)
        ell(d, [CX - 26, cy - 11, CX + 26, cy - 1], fill=top, outline=edge)
        ell(d, [CX - 12, cy - 8, CX + 12, cy - 4], fill=hi)


@cover("_pico", system=True, bg=((216, 240, 226), (150, 200, 172)))
def pico_cover(d):
    pcb, pcb_d, gold = (30, 122, 68), (14, 70, 40), (228, 196, 72)
    rr(d, [CX - 21, CY - 32, CX + 21, CY + 32], 3, fill=pcb, outline=pcb_d, width=1)
    rect(d, [CX - 9, CY - 36, CX + 9, CY - 26], fill=(198, 202, 206), outline=(110, 116, 122))
    rect(d, [CX - 5, CY - 34, CX + 5, CY - 29], fill=(128, 134, 140))       # USB mouth
    for i in range(10):                                                     # castellations
        y = CY - 24 + i * 5.4
        rect(d, [CX - 23, y, CX - 19, y + 2.6], fill=gold)
        rect(d, [CX + 19, y, CX + 23, y + 2.6], fill=gold)
    rect(d, [CX - 11, CY - 12, CX + 11, CY + 10], fill=(22, 24, 26))        # RP2040
    rect(d, [CX - 9, CY - 10, CX + 9, CY + 8], fill=(46, 48, 52))
    rect(d, [CX - 4, CY - 5, CX + 4, CY + 3], fill=(84, 88, 92))
    rect(d, [CX - 16, CY + 16, CX - 6, CY + 24], fill=(30, 32, 34))         # flash
    ell(d, [CX + 8, CY + 17, CX + 14, CY + 23], fill=(120, 214, 150))       # LED


@cover("_nds", system=True, bg=((214, 236, 250), (146, 196, 228)))
def nds_cover(d):
    body, edge, label = (56, 166, 214), (10, 44, 62), (236, 246, 252)
    # The notch is most of what makes a DS card read as a DS card, so it is cut deep.
    poly(d, [(CX - 23, CY - 31), (CX + 5, CY - 31), (CX + 23, CY - 13),
             (CX + 23, CY + 31), (CX - 23, CY + 31)], fill=body, outline=edge)
    rect(d, [CX - 15, CY - 24, CX + 12, CY - 6], fill=label, outline=edge)
    line(d, [(CX - 10, CY - 19), (CX + 7, CY - 19)], width=2, fill=(150, 176, 190))
    line(d, [(CX - 10, CY - 13), (CX + 1, CY - 13)], width=2, fill=(180, 200, 212))
    rect(d, [CX - 23, CY + 18, CX + 23, CY + 31], fill=(228, 196, 72), outline=edge)
    for i in range(9):
        x = CX - 20 + i * 4.8
        rect(d, [x, CY + 20, x + 2.6, CY + 29], fill=(150, 124, 30))


@cover("_gba", system=True, bg=((226, 218, 246), (172, 156, 214)))
def gba_cover(d):
    body, edge = (124, 88, 196), (44, 24, 78)
    rr(d, [CX - 38, CY - 18, CX + 38, CY + 18], 9, fill=body, outline=edge, width=1)
    rr(d, [CX - 15, CY - 13, CX + 15, CY + 10], 2, fill=(40, 22, 70), outline=edge)
    rect(d, [CX - 12, CY - 10, CX + 12, CY + 7], fill=(150, 220, 160))
    rect(d, [CX - 30, CY - 4, CX - 18, CY], fill=(38, 20, 64))              # d-pad
    rect(d, [CX - 26, CY - 8, CX - 22, CY + 4], fill=(38, 20, 64))
    ell(d, [CX + 22, CY - 8, CX + 30, CY], fill=(226, 84, 96), outline=edge)
    ell(d, [CX + 16, CY + 1, CX + 24, CY + 9], fill=(96, 118, 208), outline=edge)
    for i in range(4):
        line(d, [(CX - 8 + i * 5, CY + 13), (CX - 8 + i * 5, CY + 16)],
             fill=(80, 52, 140))                                            # speaker


@cover("EZ5Shell", system=True, bg=((250, 222, 222), (222, 160, 164)))
def ez5shell_cover(d):
    edge, bar, sel = (66, 12, 18), (176, 38, 52), (214, 62, 74)
    rr(d, [CX - 32, CY - 26, CX + 32, CY + 26], 2, fill=(255, 240, 238),
       outline=edge, width=1)
    rect(d, [CX - 31, CY - 25, CX + 31, CY - 14], fill=bar)
    rect(d, [CX - 27, CY - 21, CX - 9, CY - 18], fill=(248, 200, 202))      # title
    rect(d, [CX - 28, CY - 9, CX + 28, CY + 0], fill=sel, outline=None)     # selected row
    for i, y in enumerate((5, 14)):
        rect(d, [CX - 28, CY + y, CX + 28, CY + y + 6], fill=(250, 226, 226))
        rect(d, [CX - 25, CY + y + 2, CX + 6 - i * 10, CY + y + 4], fill=(214, 122, 128))


@cover("Games", system=False, bg=((222, 236, 252), (148, 186, 232)))
def games_cover(d):
    body, edge, inner = (62, 130, 205), (14, 36, 68), (22, 56, 104)
    rr(d, [CX - 30, CY - 38, CX + 30, CY - 2], 4, fill=body, outline=edge, width=1)
    rect(d, [CX - 25, CY - 34, CX + 25, CY - 6], fill=inner)
    rect(d, [CX - 23, CY - 32, CX + 23, CY - 8], fill=(255, 255, 255))
    rr(d, [CX - 30, CY + 2, CX + 30, CY + 38], 4, fill=body, outline=edge, width=1)
    rect(d, [CX - 25, CY + 6, CX + 25, CY + 34], fill=inner)
    rect(d, [CX - 23, CY + 8, CX + 23, CY + 32], fill=(232, 240, 248))
    rect(d, [CX - 15, CY + 14, CX + 7, CY + 22], fill=(232, 92, 140))       # selection
    rect(d, [CX - 15, CY + 25, CX - 1, CY + 28], fill=(160, 180, 205))
    line(d, [(CX - 30, CY), (CX + 30, CY)], width=2, fill=edge)             # hinge


@cover("Enfance", system=False, bg=((255, 236, 214), (240, 190, 150)))
def enfance_cover(d):
    fur, fur_d, muzzle, inner = (206, 142, 96), (86, 50, 32), (255, 232, 210), (238, 130, 160)
    ell(d, [CX - 32, CY - 34, CX - 10, CY - 12], fill=(162, 100, 62), outline=fur_d)
    ell(d, [CX + 10, CY - 34, CX + 32, CY - 12], fill=(162, 100, 62), outline=fur_d)
    ell(d, [CX - 27, CY - 29, CX - 15, CY - 17], fill=inner)
    ell(d, [CX + 15, CY - 29, CX + 27, CY - 17], fill=inner)
    ell(d, [CX - 28, CY - 28, CX + 28, CY + 30], fill=fur, outline=fur_d)
    ell(d, [CX - 15, CY - 1, CX + 15, CY + 23], fill=muzzle)
    ell(d, [CX - 15, CY - 15, CX - 7, CY - 5], fill=fur_d)                  # eyes
    ell(d, [CX + 7, CY - 15, CX + 15, CY - 5], fill=fur_d)
    ell(d, [CX - 13, CY - 13, CX - 10, CY - 10], fill=(255, 255, 255))
    ell(d, [CX + 9, CY - 13, CX + 12, CY - 10], fill=(255, 255, 255))
    ell(d, [CX - 6, CY + 1, CX + 6, CY + 9], fill=fur_d)                    # nose
    line(d, [(CX, CY + 9), (CX, CY + 14)], width=2, fill=fur_d)
    d.arc([(CX - 11) * SS, (CY + 7) * SS, (CX) * SS, (CY + 19) * SS], 0, 110,
          fill=fur_d, width=2 * SS)
    d.arc([(CX) * SS, (CY + 7) * SS, (CX + 11) * SS, (CY + 19) * SS], 70, 180,
          fill=fur_d, width=2 * SS)


# ----------------------------------------------------------------------------------- build

def build(name):
    fn, system, bg = COVERS[name]
    img = _gradient(*bg)
    d = ImageDraw.Draw(img)
    fn(d)
    if system:
        # Same marking as the icons, same corner, scaled to the room available here.
        gx, gy, r = COVER_VISIBLE_W - 17.0, COVER_H - 17.0, 12.0
        ell(d, [gx - r - 2.5, gy - r - 2.5, gx + r + 2.5, gy + r + 2.5], fill=GEAR_LIGHT)
        draw_gear(d, gx * SS, gy * SS, r * SS, fill=GEAR_BODY, outline=GEAR_DARK,
                  hub_fill=GEAR_DARK, hub_r=3.4 * SS)

    small = img.resize((COVER_W, COVER_H), Image.LANCZOS)
    q = small.quantize(colors=255, method=Image.MEDIANCUT, dither=Image.Dither.NONE)

    # Palette entry 0 has to be the background colour, and not whatever the quantiser
    # happened to put there.  RomBrowserTopScreenView::VBlank copies the cover's entry 0
    # straight into the sub engine's backdrop register, and the cover is drawn on an
    # affine BG where index 0 is transparent -- so entry 0 is both the colour that shows
    # through the cover and the colour behind everything else on the top screen.  Make it
    # the wash the cover already starts with and neither can look wrong.
    flat = list(q.getpalette())[: 255 * 3]
    bg = list(img.getpixel((2 * SS, 2 * SS)))
    out = Image.new("P", (COVER_W, COVER_H))
    out.frombytes(bytes(b + 1 for b in q.tobytes()))
    out.putpalette(bg + flat + [0] * (768 - 3 - len(flat)))
    return out


if __name__ == "__main__":
    outdir = sys.argv[1]
    cols, zoom = 4, 2
    rows = (len(COVERS) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * COVER_W * zoom, rows * COVER_H * zoom), (24, 24, 28))
    for i, name in enumerate(COVERS):
        img = build(name)
        write_cover_bmp("%s/%s.cover.bmp" % (outdir, name), img)
        prev = img.convert("RGB").resize((COVER_W * zoom, COVER_H * zoom), Image.NEAREST)
        # Mark where the launcher stops drawing.
        pd = ImageDraw.Draw(prev)
        pd.line([COVER_VISIBLE_W * zoom, 0, COVER_VISIBLE_W * zoom, COVER_H * zoom],
                fill=(255, 0, 128))
        sheet.paste(prev, ((i % cols) * COVER_W * zoom, (i // cols) * COVER_H * zoom))
        print("%-10s written" % name)
    sheet.save("%s/_cover_sheet.png" % outdir)
