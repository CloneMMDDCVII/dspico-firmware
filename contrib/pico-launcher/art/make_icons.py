#!/usr/bin/env python3
"""Draw the 32x32 4bpp folder icons for Pico Launcher and write them as icon.bmp.

Six of the eight folders are system folders and carry a gear in the bottom-right corner.
Their symbols are composed inside the top-left 26x26 so the gear has a corner to sit in
without covering the part that identifies the folder.  Games and Games/Enfance carry no
gear: they are the two folders the user is meant to be in.
"""
import sys
from PIL import Image, ImageDraw

from art_common import ICON_W, ICON_H, write_icon_bmp, stamp_icon_gear

PAD = [(0, 0, 0)] * 16


def canvas(palette):
    img = Image.new("P", (ICON_W, ICON_H), 0)
    flat = []
    for rgb in palette:
        flat.extend(rgb)
    img.putpalette(flat + [0] * (768 - len(flat)))
    return img, ImageDraw.Draw(img)


def pal16(*colours):
    """Pad a colour list out to 16 entries, leaving 13-15 free for the gear."""
    colours = list(colours)
    assert len(colours) <= 13, "indices 13-15 are reserved for the system gear"
    return colours + PAD[: 16 - len(colours)]


ICONS = {}


def icon(name, system):
    def deco(fn):
        ICONS[name] = (fn, system)
        return fn
    return deco


# Index 0 is the sprite transparency index, so it is never drawn with.


@icon("SAVE", system=True)
def save_icon():
    # A floppy disk.  Still the clearest "this is where saves live" pictogram there is.
    pal = pal16((0, 0, 0), (26, 92, 96), (38, 132, 138), (58, 176, 184), (96, 208, 214),
                (235, 240, 240), (200, 210, 212), (150, 162, 165), (18, 62, 66),
                (255, 255, 255), (120, 132, 134))
    img, d = canvas(pal)
    d.rectangle([1, 2, 24, 25], fill=3, outline=1)          # body
    d.rectangle([2, 3, 23, 7], fill=2)                      # top bevel
    d.rectangle([6, 2, 18, 11], fill=6, outline=1)          # shutter housing
    d.rectangle([12, 3, 17, 10], fill=10)                   # metal slider
    d.rectangle([8, 4, 11, 9], fill=8)                      # shutter cut-out
    d.rectangle([4, 15, 21, 25], fill=5, outline=1)         # label
    for i, y in enumerate((18, 21)):
        d.line([6, y, 19 - i * 4, y], fill=7)               # ruled lines
    return img, pal


@icon("ROMDAT", system=True)
def romdat_icon():
    # A database: stacked platters.  SAVE is the user's data, this is the launcher's, and
    # the two need to look like different kinds of storage rather than two floppies.
    pal = pal16((0, 0, 0), (120, 80, 12), (186, 128, 26), (228, 168, 48), (248, 206, 108),
                (255, 236, 186), (96, 62, 8), (255, 255, 255), (208, 148, 36))
    img, d = canvas(pal)
    for i, top in enumerate((16, 10, 4)):
        d.rectangle([2, top + 3, 23, top + 7], fill=3 if i else 2, outline=1)
        d.ellipse([2, top, 23, top + 6], fill=4, outline=1)     # platter top
        d.ellipse([9, top + 2, 16, top + 4], fill=5)            # spindle highlight
    d.line([4, 22, 6, 22], fill=6)
    return img, pal


@icon("_pico", system=True)
def pico_icon():
    # The Pico board itself: green PCB, castellated edges, USB at the top.  This folder is
    # the launcher's own machinery, so it gets the launcher's own hardware.
    pal = pal16((0, 0, 0), (12, 62, 36), (22, 104, 58), (36, 150, 84), (110, 206, 146),
                (206, 240, 220), (198, 202, 206), (128, 134, 140), (228, 196, 72),
                (250, 250, 250))
    img, d = canvas(pal)
    d.rounded_rectangle([2, 1, 23, 25], radius=2, fill=2, outline=1)    # PCB
    d.rectangle([8, 0, 17, 5], fill=6, outline=7)                       # USB shell
    d.rectangle([10, 1, 15, 3], fill=7)
    for y in range(6, 24, 3):
        d.rectangle([1, y, 3, y + 1], fill=8)                           # castellations
        d.rectangle([22, y, 24, y + 1], fill=8)
    d.rectangle([8, 9, 17, 18], fill=1, outline=1)                      # RP2040
    d.rectangle([9, 10, 16, 17], fill=3)
    d.rectangle([11, 12, 14, 15], fill=4)
    d.rectangle([5, 21, 8, 23], fill=5)                                 # flash chip
    return img, pal


@icon("_nds", system=True)
def nds_icon():
    # A DS game card, notched corner and all.
    pal = pal16((0, 0, 0), (16, 68, 96), (28, 116, 160), (56, 166, 214), (120, 208, 240),
                (206, 240, 252), (240, 240, 240), (140, 150, 156), (10, 44, 62))
    img, d = canvas(pal)
    d.polygon([(4, 1), (17, 1), (22, 6), (22, 25), (4, 25)], fill=3, outline=1)
    d.rectangle([7, 5, 19, 13], fill=5, outline=1)          # label area
    d.rectangle([9, 17, 17, 22], fill=2, outline=1)         # contacts block
    for x in (10, 12, 14, 16):
        d.line([x, 18, x, 21], fill=7)
    return img, pal


@icon("_gba", system=True)
def gba_icon():
    # A Game Boy Advance, seen head on.
    pal = pal16((0, 0, 0), (52, 30, 92), (86, 54, 148), (124, 88, 196), (170, 140, 224),
                (226, 216, 244), (150, 220, 160), (40, 22, 70), (226, 84, 96),
                (96, 118, 208))
    img, d = canvas(pal)
    d.rounded_rectangle([0, 5, 25, 21], radius=5, fill=3, outline=1)
    d.rectangle([7, 8, 19, 18], fill=7, outline=1)          # screen bezel
    d.rectangle([9, 10, 17, 16], fill=6)                    # screen
    d.rectangle([2, 11, 5, 13], fill=1)                     # d-pad
    d.rectangle([3, 10, 4, 14], fill=1)
    d.rectangle([21, 10, 23, 12], fill=8)                   # A
    d.rectangle([20, 14, 22, 16], fill=9)                   # B
    return img, pal


@icon("EZ5Shell", system=True)
def ez5shell_icon():
    # The EZ-Flash shell: a menu on a screen.  It used to be a cartridge with a gear on
    # it, but the gear is now the marking every system folder carries, and a second
    # cartridge would only have competed with _nds.
    # Crimson rather than the amber it started in: ROMDAT is gold, and two warm-orange
    # icons sitting next to each other in the grid defeats the point of drawing them.
    pal = pal16((0, 0, 0), (110, 20, 30), (176, 38, 52), (214, 62, 74), (240, 128, 132),
                (255, 238, 236), (66, 12, 18), (255, 255, 255), (150, 30, 42))
    img, d = canvas(pal)
    d.rounded_rectangle([1, 2, 24, 24], radius=2, fill=5, outline=6)    # screen
    d.rectangle([2, 3, 23, 8], fill=2)                                  # title bar
    d.rectangle([4, 5, 11, 6], fill=4)
    d.rectangle([3, 11, 22, 14], fill=3, outline=1)                     # selected row
    for y in (16, 19):
        d.line([4, y, 21, y], fill=8)                                   # other rows
        d.line([4, y + 1, 15, y + 1], fill=4)
    return img, pal


@icon("Games", system=False)
def games_icon():
    # A DS, open.  The folder that actually holds the games gets the console itself, and
    # no gear: this is one of the two the user is meant to be in.
    pal = pal16((0, 0, 0), (20, 52, 96), (34, 86, 152), (62, 130, 205), (120, 178, 235),
                (232, 240, 248), (255, 255, 255), (146, 160, 176), (14, 36, 68),
                (232, 92, 140))
    img, d = canvas(pal)
    d.rounded_rectangle([4, 1, 27, 14], radius=3, fill=3, outline=1)   # top half
    d.rectangle([7, 3, 24, 12], fill=8, outline=1)
    d.rectangle([8, 4, 23, 11], fill=6)                                # top screen
    d.rounded_rectangle([4, 16, 27, 30], radius=3, fill=3, outline=1)  # bottom half
    d.rectangle([7, 18, 24, 27], fill=8, outline=1)
    d.rectangle([8, 19, 23, 26], fill=5)                               # bottom screen
    d.rectangle([12, 21, 19, 24], fill=9)                              # pink selection
    d.line([4, 15, 27, 15], fill=1)                                    # hinge
    return img, pal


@icon("Enfance", system=False)
def enfance_icon():
    # A teddy bear: the one folder aimed at a child, so it should read as a child's.
    pal = pal16((0, 0, 0), (110, 62, 40), (162, 100, 62), (206, 142, 96), (236, 190, 150),
                (255, 232, 210), (60, 34, 22), (238, 130, 160), (255, 255, 255))
    img, d = canvas(pal)
    d.ellipse([3, 4, 12, 13], fill=2, outline=6)             # left ear
    d.ellipse([19, 4, 28, 13], fill=2, outline=6)            # right ear
    d.ellipse([5, 6, 10, 11], fill=7)
    d.ellipse([21, 6, 26, 11], fill=7)
    d.ellipse([4, 7, 27, 29], fill=3, outline=6)             # head
    d.ellipse([9, 17, 22, 26], fill=5)                       # muzzle
    d.ellipse([10, 13, 13, 17], fill=6)                      # eyes
    d.ellipse([18, 13, 21, 17], fill=6)
    d.point((11, 14), fill=8)
    d.point((19, 14), fill=8)
    d.ellipse([14, 18, 17, 21], fill=6)                      # nose
    d.line([15, 21, 15, 23], fill=6)
    d.arc([11, 20, 15, 25], 0, 130, fill=6)                  # mouth
    d.arc([16, 20, 20, 25], 50, 180, fill=6)
    return img, pal


def build(name):
    fn, system = ICONS[name]
    img, pal = fn()
    if system:
        pal = stamp_icon_gear(img, pal)
    return img, pal


if __name__ == "__main__":
    outdir = sys.argv[1]
    zoom = 8
    sheet = Image.new("RGB", (len(ICONS) * ICON_W * zoom, ICON_H * zoom), (24, 24, 28))
    for i, name in enumerate(ICONS):
        img, pal = build(name)
        write_icon_bmp("%s/%s.icon.bmp" % (outdir, name), img, pal)
        sheet.paste(img.convert("RGB").resize((ICON_W * zoom, ICON_H * zoom),
                                              Image.NEAREST), (i * ICON_W * zoom, 0))
        print("%-10s written" % name)
    sheet.save("%s/_icon_sheet.png" % outdir)
