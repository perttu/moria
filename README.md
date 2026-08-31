# Moria Amiga

A preservation-oriented port of **Amiga Moria Graphics 1.2** (Henrik Harmsen's
graphical frontend, over UMoria 5.5) to modern Linux, macOS and the browser.

The governing rule is a boundary, not a feature list:

> Henrik owns presentation. UMoria owns gameplay.

Nothing emulates an Amiga. `amiga.c` is read as a specification and is never
compiled; Intuition, `graphics.library`, `console.device`, `iff.library` and
the hand-written bitplane blitters stop at the port boundary. What crosses is
the 640x200 composition, the 66x22 viewport, the GFX_CORR tile mapping, the
palette, the colour semantics and the reduced 1:4 overview.

## Current state

`amiga-gfx-test` — the frontend with no game engine behind it. It answers
"can we reproduce Henrik's frontend accurately?" before any Umoria code is
touched, so that engine, SDL, assets and Amiga compatibility are never being
debugged all at once.

It renders four screens into a real 640x200 framebuffer: the original title,
a GFX_CORR atlas viewer, a stand-in dungeon drawn from the real tiles, and the
reduced overview map.

## Historical inputs

The original source and artwork are **not** committed here; their licensing
has not been reviewed (see NOTES.md). Point the build at your own copies:

```
-DMORIA_HISTORICAL_DIR=/path/to/1.1/source     # contains amiga_corrlist.c
-DMORIA_ASSET_DIR=/path/to/1.2/Moria           # contains the three .iff files
```

Everything derived from them — the GFX_CORR table, the embedded artwork — is
generated into the build directory at compile time and never checked in.

## Building

SDL3 is vendored as a submodule, so no Homebrew, apt or system SDL is needed:

```bash
git submodule update --init --depth 1
```

### Linux

```bash
cmake -S . -B build-linux -DCMAKE_BUILD_TYPE=Release \
    -DMORIA_HISTORICAL_DIR=... -DMORIA_ASSET_DIR=...
cmake --build build-linux -j"$(nproc)"
./build-linux/amiga-gfx-test
```

Optional X11 extensions that are missing are detected and switched off rather
than failing the configure step; the build prints the `apt install` line for
whatever it had to disable. For a full-featured desktop build:

```bash
sudo apt install libxcursor-dev libxi-dev libxrandr-dev libxfixes-dev \
                 libxss-dev libxtst-dev libxkbcommon-dev libwayland-dev
```

### macOS

```bash
cmake -S . -B build-mac -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DMORIA_HISTORICAL_DIR=... -DMORIA_ASSET_DIR=...
cmake --build build-mac
./build-mac/amiga-gfx-test
```

Universal (Intel and Apple Silicon in one binary):

```bash
cmake -S . -B build-universal -G Ninja -DCMAKE_BUILD_TYPE=Release \
    '-DCMAKE_OSX_ARCHITECTURES=arm64;x86_64' \
    -DMORIA_HISTORICAL_DIR=... -DMORIA_ASSET_DIR=...
```

### Browser

```bash
emcmake cmake -S . -B build-web -DCMAKE_BUILD_TYPE=Release \
    -DMORIA_HISTORICAL_DIR=... -DMORIA_ASSET_DIR=...
cmake --build build-web
cd build-web && python3 -m http.server 8000
```

Then open `http://localhost:8000/amiga-gfx-test.html`. Opening the file
directly will not work: browsers refuse `.wasm` over `file://`.

## Running

```
amiga-gfx-test [--screen title|tiles|dungeon|overview] [--scale N]
               [--fullscreen] [--headless] [--screenshot FILE]
```

| key | action |
| --- | --- |
| arrows / numpad | move |
| `M` | reduced overview map |
| `T` | GFX_CORR atlas viewer |
| space | leave the title screen |
| Cmd+Enter / Ctrl+Enter | toggle fullscreen |
| Esc | quit |

`--headless --screenshot out.bmp` renders one screen without a display and
writes the 640x200 framebuffer exactly as composed, before any scaling. That
is the hook the pixel regression tests use, and it works over SSH and in CI.

## Tests

```bash
ctest --test-dir build-linux --output-on-failure
```

For a preservation port these matter more than conventional unit tests: the
goal is that the pixels do not move.

| test | what it actually checks |
| --- | --- |
| `smoke-start` | the binary comes up: `--help` exits zero, a bad argument does not, all four screens render at 640×200, `--scale 3` leaves the virtual screen alone, and it starts against a real X server rather than only the dummy driver |
| `gfx-corr` | the tile mapping, the extended codes above 127, and the seed parameters, against values transcribed from the 1992 source |
| `pixel-screens` | the rendered title against `moria_title.iff` itself; named dungeon cells against the atlas tile that belongs at that screen position; each whole screen against a reviewed golden hash; the X11 render against the headless one |
| `tool-iff-convert` | ILBM masking modes 0, 1 and 2 survive conversion into both output formats |
| `tool-gen-font` | non-8x8 and truncated fonts are refused rather than cropped or misaligned |
| `tool-gen-gfx-corr` | mutations of the historical source — a removed seed fixup, a changed `randint` range, a dropped mapping — are caught |

The golden hashes in `tests/golden_screens.json` are a record of screens
somebody looked at, so they are not regenerated automatically. After a
deliberate visual change:

```bash
cmake --build build-linux --target update-screen-goldens
```

then review the BMPs in `build-linux/screens/` before committing the new
hashes.

`smoke-start` uses an already-built binary. To check that a clean tree
configures and compiles from nothing — it rebuilds SDL, so it is off by
default:

```bash
cmake -S . -B build-linux -DMORIA_TEST_CLEAN_BUILD=ON ...
ctest --test-dir build-linux -R build-from-clean
```

or directly, without CMake:

```bash
python3 tests/build_and_start.py --source . \
    --historical /path/to/1.1/source --assets /path/to/1.2/Moria
```

## Layout

```
src/frontend/     the display API and its SDL3 implementation
src/tools/        amiga-gfx-test
tools/            IFF converter, GFX_CORR extractor, font generator
tests/            table assertions and screenshot tests
vendored/SDL/     SDL3, as a submodule
```
