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

Two binaries.

**`moria-amiga`** — Umoria 5.7.15 running on the Amiga frontend: Henrik's
tiles, his extended graphics for 96 creatures and 139 objects, his semantic
colours, his 1:4 overview map, and save/load. Builds natively and for the
browser, where its character creation screen is byte-identical to the native
one and saves persist across page loads.

**`amiga-gfx-test`** — the frontend with no engine behind it, which is what
proved the artwork and geometry before any Umoria code was touched. It renders
four screens into a real 640x200 framebuffer: the original title, a GFX_CORR
atlas viewer, a stand-in dungeon, and the reduced overview map. It is also the
browser target.

Umoria's sources are copied into the build tree by `tools/patch_umoria.py`,
which applies a handful of exact substitutions on the way through: `ui_io.cpp`
draws through the frontend, `dungeon.cpp` hands the reduced map over, and
`headers.h` learns that Emscripten exists. Every substitution must match
exactly or the build fails. Its `main()` is replaced by `src/engine/main.cpp`.
**No gameplay source is modified** — everything not named in that script is
byte-identical to upstream.

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

Then open `http://localhost:8000/moria-amiga.html` for the game, or
`amiga-gfx-test.html` for the frontend demo. Opening the file directly will
not work: browsers refuse `.wasm` over `file://`.

The game page has three tabs — the game itself, a searchable **command
reference**, and a **races and classes** table. Both reference panels are
generated at build time from Umoria's own `data/help.txt`, `data/rl_help.txt`
and `data_player.cpp`, so they cannot drift from the game. They are linkable:
`#commands` and `#character`.

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
| `web-smoke` | the WebAssembly build in headless Chrome: the canvas draws the title pixel-identically to `moria_title.iff`, Space reaches the game through the browser event path, the dungeon screen is byte-identical to the native render, the real game reaches character creation, a save is written to browser storage and read back, and a save planted in storage is restored and resumed |
| `keys` | every command character a player needs, including `*`, `?` and the `>` / `<` stair keys |
| `tool-web-help` | the browser page's reference panels, against values that can be confirmed by reading the game: a Half-Troll gets 12 hit points, a Dwarf cannot be a Mage |
| `game-screens` | the real game, driven with a fixed seed through character creation into the town: the screens match reviewed goldens, two runs agree, and **every drawn cell of the viewport is a tile from the atlas rather than a character from the font** |
| `colours` | every colour rule quoted from Amiga.doc and Update.doc, then a render through the real shim: at 20% health the hit point line comes out red, not white |
| `sprites` | Henrik's extended display codes — 96 creatures and 139 objects — resolved by name against Umoria's own tables, each with a GFX_CORR tile |
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

`web-smoke` needs an Emscripten build to point at, and a Chrome or Chromium
binary (it will use one from the Playwright cache if there is no system one):

```bash
cmake -S . -B build-linux -DMORIA_WEB_BUILD_DIR=$PWD/build-web ...
ctest --test-dir build-linux -R web-smoke
```

or directly:

```bash
python3 tests/web_smoke.py --build-web build-web --assets /path/to/1.2/Moria \
    --golden tests/golden_screens.json
```

## Layout

```
src/frontend/     the display API and its SDL3 implementation
src/tools/        amiga-gfx-test
tools/            IFF converter, GFX_CORR extractor, font generator
tests/            table assertions and screenshot tests
vendored/SDL/     SDL3, as a submodule
```
