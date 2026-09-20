# Putting your image on the Pico Launcher boot splash

These files live here so they survive a `rm -rf ~/Games/PicoDS` and so you can fetch them
with one command instead of copying them out of a chat window. Nothing in this directory
is part of the DSpico firmware; it is a delivery drop for the launcher work.

## Get the files

```bash
BASE=https://raw.githubusercontent.com/CloneMMDDCVII/dspico-firmware/claude/project-thread-kme98u/contrib/pico-launcher

mkdir -p ~/Downloads
curl -fL -o ~/Downloads/custom-splash.patch  $BASE/custom-splash.patch
curl -fL $BASE/folder-icons.zip.base64 | base64 -d > ~/Downloads/folder-icons.zip

sha256sum ~/Downloads/custom-splash.patch ~/Downloads/folder-icons.zip
# 828840a97f90e915dec12db6ba96e1fc891b9e41d654273fa826f98c7c8082b2  custom-splash.patch
# 2b0ee99dfdf97b3de0388af4d5a95683f837265c82546b4f18669bb5dea06bb1  folder-icons.zip
```

The icons are stored base64-encoded because this session can only write text files to
GitHub; the `base64 -d` above turns it back into the same zip you already have.

If the hashes do not match, stop: the patch carries a binary PNG and a mangled copy will
either fail `git apply` or, worse, apply and produce a corrupt image.

## What's in the patch

`custom-splash.patch` changes two things:

- `arm9/gfx/splashTop.png` becomes your image, already converted to what grit expects:
  256×192, 8-bit indexed, 251 colours, no alpha.
- `arm9/source/App.cpp` moves the splash's tilemap from 0x3000 to 0xC000 in sub BG VRAM,
  and updates the screen base in `REG_BG1CNT_SUB` to match (0x0680 → 0x1880).

That second change is the one that makes this possible at all. At 0x3000 the tile data
had room for 192 unique 8bpp tiles; the stock splash uses 150, and yours needs 563. At
0xC000 there is room for a full screen of 768, so any 256-colour image fits from now on.
Two `static_assert`s now fail the build if a future image ever overruns it, rather than
letting it corrupt the screen at runtime.

## Build it

```bash
cd ~/Games/PicoDS
git clone https://github.com/LNH-team/pico-launcher
cd pico-launcher
git checkout develop
git rev-parse --short HEAD        # dc64a34, or newer
git submodule update --init

git apply ~/Downloads/custom-splash.patch
git status --short                # exactly two M lines, nothing else
```

`git rev-parse` is the check that catches a stale clone. The patch is cut against
`develop` at dc64a34; the folder `icon.bmp` support it relies on is not in any tagged
release, so a v1.3.0 checkout will build but will ignore the icons.

Then build it. Podman needs no toolchain on the host:

```bash
podman run --rm -v "$PWD":/work:Z -w /work \
  docker.io/skylyrac/blocksds:slim-latest make
```

Or, with the Wonderful Toolchain installed locally:

```bash
source /opt/wonderful/bin/wf-env      # or export BLOCKSDS / BLOCKSDSEXT by hand
make
```

Nothing here needs a BIOS or any keys.

The build produces `LAUNCHER.nds`. That is what goes on the card root as `_picoboot.nds`:

```bash
cp LAUNCHER.nds /run/media/$USER/<your card>/_picoboot.nds
```

Keep your current `_picoboot.nds` somewhere first. Putting it back is the whole of the
undo.

The folder icons go on the card in the same pass, each `icon.bmp` into the folder it
names:

```bash
cd /run/media/$USER/<your card>
unzip -o ~/Downloads/folder-icons.zip
```

Those need this same `develop` build to show up at all — see the note about tagged
releases above.

## What I verified, and what I didn't

Verified here, using the real `grit` from the BlocksDS sources rather than an
approximation of it:

- Your image converts to 36,032 bytes of tiles, a 2,048-byte tilemap and a 512-byte
  palette. 36,032 fits under 0xC000 with room to spare, and would have overrun the old
  0x3000 by nearly three times.
- I reassembled those three files back into a picture the way the DS hardware will, tile
  indices, flips, palette and all. It comes back as your image, with no pixel off by more
  than 7 per channel — which is exactly the DS's 5-bit-per-channel colour depth and
  nothing else. `topsplash-as-the-DS-will-draw-it.png` is that reassembly, so it is a
  fair preview of what the screen will actually show.
- The register arithmetic: 0xC000 / 2048 = screen base 24, giving `REG_BG1CNT_SUB` =
  0x1880, with character base 0 and the 256-colour bit unchanged from 0x0680.

Not verified, because I can't:

- **The build itself.** BlocksDS needs picolibc, which isn't available in my environment,
  so I could build its host tools but not link a DS binary. The patch is a two-line change
  plus an image, but it has not been through a compiler.
- **Anything on hardware.** First boot is the test.

One thing to watch on that first boot: the launcher reuses this VRAM later for the rom
browser's own tilemap at 0x3800 and cover art at 0x4000, and for theme previews across
0x0–0x17FFF. All of that runs after the splash has gone, so moving the map to 0xC000
should be invisible to it. If you see corruption in the browser rather than the splash,
that assumption is where to look first.
