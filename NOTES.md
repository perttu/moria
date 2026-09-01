# NOTES

Preservation port of Amiga Moria Graphics 1.2 (Henrik Harmsen's frontend) plus
UMoria, to SDL3 on Linux, macOS and the browser. Full brief supplied by the
owner 2026-09-01. Governing boundary: **Henrik owns presentation, UMoria owns
gameplay.** No emulation; `amiga.c` is the specification, never compiled.

Build and run instructions live in README.md.

## Where this actually is

**Milestones 1-3 of 14. There is no game here yet.**

The brief's first implementation target is finished: `amiga-gfx-test`, the
frontend proved out against the real artwork with nothing behind it. That
answers "can we reproduce Henrik's frontend?" — yes, on Linux and in the
browser. It does not touch the second question, "can Umoria drive that
frontend?", because **no Umoria is vendored in this repository at all.**

Everything the game does — walking, monsters, items, stores, saving — is
absent. The dungeon on screen is a hard-coded stand-in in
`src/tools/gfx_test_main.cpp`, and the stats beside it are invented strings.

| # | milestone | state |
| --- | --- | --- |
| 1 | asset viewer | done |
| 2 | tile atlas viewer | done |
| 3 | static Amiga screen | done |
| 4 | keyboard frontend | keys map to Moria codes, but into the stand-in |
| 5 | playable town | not started |
| 6 | playable dungeon | not started |
| 7 | special graphics | table extracted; nothing assigns codes to monsters |
| 8 | overview map | draws a fake level |
| 9 | full Amiga UI | fake stats, no message system |
| 10 | save/load | not started |
| 11 | macOS .app | blocked: no Mac here |
| 12 | Emscripten | done, verified in headless Chrome |
| 13 | IndexedDB saves | not started |
| 14 | pixel regression tests | done |

Milestones 5-10 and 13 all wait on the same thing: an engine wired to
`ui.hpp`.

### Done so far

- SDL3 vendored; frontend, display API, 640x200 virtual screen, letterboxing
- `tools/iff_convert.py`, `tools/gen_gfx_corr.py`, `tools/gen_font.py`
- Linux build works without the full X11 -dev set
- Emscripten build, running and pixel-checked in headless Chrome
- Test suite: `gfx-corr`, `pixel-screens`, `smoke-start`, `web-smoke`, the
  three tool suites, and an opt-in `build-from-clean`

### Next

- [ ] Vendor modern Umoria (the brief names `dungeons-of-moria/umoria`)
- [ ] Survey its display layer and map every terminal operation onto `ui.hpp`
- [ ] Milestone 4: real keys into the real engine
- [ ] Milestones 5-6: playable town, then dungeon
- [ ] Milestone 7: assign Henrik's extended display codes at the presentation
      layer, from monster identity — never by touching monster data
- [ ] macOS build and `.app` bundle — needs the owner's Mac

### Verified, and how

- **The rendered title screen is pixel-identical to `moria_title.iff`.** Zero
  differing pixels across 640x200 outside the one caption row the test app
  adds itself. This is the acceptance criterion from the brief, met for the
  title. It is now asserted by `pixel-screens` rather than left as a one-off
  observation.
- The X11 window path and the headless software path produce byte-identical
  640x200 output (observed under Xvfb, and now asserted by the same test).
- The dungeon screen renders the real tiles on the real geometry: message line
  at row 0, stat sidebar in columns 0-12, 66x22 viewport from column 13/row 1.
- The three Python tool suites pass: 13 converter tests, 10 font tests, 9
  extractor tests, including every mutation listed below under "caught by".

- `ctest` is 7/7 on Linux, with the browser test enabled via
  `-DMORIA_WEB_BUILD_DIR`. `tests/golden_screens.json` records screens that
  were rendered and looked at.
- Both mutation controls were run and both fail as intended: replacing
  `show_title()` with a no-op reports 13391 differing title pixels, and
  changing `kMapColOffset` from 13 to 14 is caught by the cell check
  ("player '@' is not drawn at column 21, row 9") independently of the golden
  hash, so regenerating goldens cannot hide a moved viewport.
- `build-from-clean` passes: `cmake --fresh` into an empty directory,
  through SDL, to a binary that starts.

- **The browser build runs, and renders the same pixels as the native one.**
  Headless Chrome loads the WebAssembly build, draws the title
  pixel-identically to `moria_title.iff`, accepts a Space keypress through the
  browser event path, and the resulting dungeon screen is byte-identical to
  the native render. That is the brief's "native and browser differ only in
  outer platform integration", demonstrated rather than assumed. Earlier
  attempts failed for tooling reasons only: node has no canvas, and headless
  Firefox timed out with no output.

### Not verified
- macOS: no Mac here. The CMake is conventional but unexercised.
- No display on this host, so the window has never been seen by a human at a
  real resolution — only Xvfb and the dummy driver.

### Caught by the tool tests

The mutations below all produce a build that looks fine and renders something
plausible, which is why they are tested rather than trusted:

- the seed fixup removed, or its comparisons reversed, or `cx -= 6` changed
- `randint(33)` changed to `randint(32)`
- an explicit GFX_CORR mapping dropped or altered
- an 8x16 font substituted for the 8x8 one, or a font truncated by one byte
- ILBM transparency discarded (both tile atlases are masking mode 2)

## The engine, and where it joins the frontend

`vendored/umoria` is upstream `dungeons-of-moria/umoria` at **5.7.15**, as the
brief specifies. Vendored 2026-09-01, not yet built or wired to anything.

Survey of what connecting it involves:

- **The terminal seam is narrow and already isolated.** Curses appears in only
  three files: `src/ui_io.cpp`, `src/curses.h`, and one use in
  `src/spells.cpp`. Everything else goes through about thirty functions
  declared at the top of `src/ui.h` — `putString`, `addChar`, `panelPutTile`,
  `getKeyInput`, `clearScreen`, `moveCursor` and friends. Reimplementing those
  against `ui.hpp` is the whole of milestone 4, and no gameplay file needs to
  change.
- **`panelPutTile(char ch, Coord_t coord)` is the hook for `ui::tile`.** It is
  how the dungeon map draws one cell, which is exactly where Henrik's
  `putgfx()` sat.
- **The geometry already matches.** `src/dungeon.h` has
  `SCREEN_HEIGHT = 22`, `SCREEN_WIDTH = 66` — the same 66x22 panel as Henrik's
  `screen[66][22]`. No viewport rework needed; only the origin offset
  (column 13, row 1) has to be applied when mapping panel coordinates to the
  640x200 screen.
- The higher-level drawing — `drawDungeonPanel`, the `printCharacter*` stat
  block — is built on those primitives and should come along unchanged.

Open: 5.7.15 has drifted from the 5.5 the 1.2 assets target. The brief accepts
that ("modern/original UMoria rules + Henrik presentation + 1.2 assets"), but
any place where 5.7 changed a display character is a place the GFX_CORR
mapping could silently miss.

## Historical inputs

Supplied by the owner 2026-09-01 as uploads. They are **not committed**: the
brief flags that Henrik's artwork needs its own provenance review, and
uploads are the owner's to add. The build takes paths instead:
`-DMORIA_HISTORICAL_DIR` and `-DMORIA_ASSET_DIR`.

- `source.zip` — Amiga Moria Graphics **1.1** source (UMoria 5.4 base), 57
  files including `amiga.c`, `amiga_corrlist.c`, `amiga_menu.c`, `fastcp.s`.
- `Moria.zip` — **1.2** binary distribution: three `.iff` atlases, the Amiga
  executable, `Docs/`. `news` reads "Amiga graphics 'Umoria 5.5' V1.2".

Established from them:

- `init_GFX_CORR()` assigns **230 display codes** explicitly, including all
  128 codes in the extended 128-255 block. (An earlier note said 231; that
  counted `'i'` and the loop variable `i` as separate keys.)
- The hallucination hack, preserved verbatim: seed all 256 entries with
  `cx=randint(33)-1`, `cy=randint(7)-1`, then `if ((cx<20) && (cx>13)) cx -= 6;`
- `putgfx()` proves the atlas indexing: `GFX_CORR[0][c]` is the tile column and
  `GFX_CORR[1][c]` the tile row, both in 8-pixel cells.
- `mvaddchg()` indexes `screen[col-13][row-1]`, fixing the viewport at 66x22
  with its origin at column 13, row 1.
- Overview: `x_off = 122`, `y_off = 34`, two pixels per dungeon cell.
- Atlases: `moria_gfx.iff` 320x56 (40x7 cells of 8x8), `moria_gfxsmall.iff`
  80x14 (40x7 cells of 2x2), `moria_title.iff` 640x200. All 4-plane, 16-colour.
- `moria_gfx.iff`'s CMAP is byte-identical to `ColourTable[16]` in `amiga.c`,
  so tiles and text share one palette. `moria_title.iff` has its own palette,
  which is why `amiga.c` keeps a separate `ColourTableTitle[16]`.

## Ideas

- The tile viewer could show which codes are seeded rather than mapped; that
  is the set hallucination relies on.
- `tests/compare_screens.py` names two dungeon cells explicitly. Widening that
  to every non-blank cell would make a viewport regression impossible to miss,
  at the cost of a slower test.

## Questions

1. ~~Do we have `amiga_corrlist.c`?~~ Resolved — full table present.
2. ~~IFF or PNG?~~ Resolved — raw ILBM; `tools/iff_convert.py` handles it.
3. **Font.** `src/frontend/font8x8.generated.hpp` is currently the IBM VGA 8x8
   font from this machine's `console-setup` package. Right metrics, wrong
   glyphs: the Amiga draws text with ROM-resident Topaz, which ships in
   neither archive. Either point `tools/gen_font.py` at real Topaz data, or
   extract it from a Kickstart ROM you own. Its licence also needs to join the
   review below.
4. **Message colours.** Amiga.doc names them (white normal, red danger, yellow
   warning, green success, light blue kill, dark red stat loss, blue stat
   gain) and the palette matches those names cleanly, but the game passes bare
   integers with no named constants. Only index 1 = Normal is confirmed from
   source (`io.c` passes 1 for the uncoloured " -more-"). The rest are
   inferred in `amiga_palette.hpp` and want checking against call sites.
5. ~~UMoria base?~~ Answered by the brief itself, which names
   `dungeons-of-moria/umoria`. Vendored at 5.7.15; no longer an open question.
6. **Licensing**, before anything is published: Henrik's artwork, the 1.1
   source, and now the placeholder console font. Building privately is fine;
   distribution is not covered by Umoria's GPL relicensing.

## For me
