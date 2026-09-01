# NOTES

Preservation port of Amiga Moria Graphics 1.2 (Henrik Harmsen's frontend) plus
UMoria, to SDL3 on Linux, macOS and the browser. Full brief supplied by the
owner 2026-09-01. Governing boundary: **Henrik owns presentation, UMoria owns
gameplay.** No emulation; `amiga.c` is the specification, never compiled.

Build and run instructions live in README.md.

## Now

Milestone 1 (asset viewer) through milestone 3 (static Amiga screen) are done
and verified on Linux, as `amiga-gfx-test`.

- [x] Verify the toolchain and SDL's Linux dependencies on this host
- [x] Vendor SDL3 as a submodule (`vendored/SDL`)
- [x] `tools/iff_convert.py` — ILBM decoder to PNG and to embeddable RGBA
- [x] `tools/gen_gfx_corr.py` — extract GFX_CORR from `amiga_corrlist.c`
- [x] `tools/gen_font.py` — 8x8 font header (placeholder; see below)
- [x] Narrow display API (`src/frontend/ui.hpp`), no SDL above it
- [x] SDL3 frontend: 640x200 render target, nearest neighbour, 3.2:1 letterbox
- [x] `amiga-gfx-test` with title / tiles / dungeon / overview screens
- [x] Keyboard: arrows and numpad to Moria direction digits, modifiers carried
- [x] Linux build works without the full X11 -dev set (missing extensions are
      probed and switched off, with the `apt install` line printed)
- [x] Tests: GFX_CORR assertions and four headless 640x200 screenshots
- [x] Emscripten build — compiles, and verified running in headless Chrome
- [x] Review round 1: replace exit-code screenshot tests with pixel
      comparisons; decode ILBM transparency; harden the generators
- [x] Build-and-start tests: `smoke-start` on every ctest run, plus an opt-in
      `build-from-clean` that configures and compiles from nothing
- [x] `web-smoke`: the browser build in headless Chrome, compared against both
      the original artwork and the native render
- [ ] macOS build and `.app` bundle — needs the owner's Mac
- [ ] Milestone 4 onward: connect the frontend to Umoria

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
5. **UMoria base** — upstream `dungeons-of-moria/umoria` 5.7.x restoration, as
   the brief says, accepting its deltas from the 5.5 the 1.2 assets target?
6. **Licensing**, before anything is published: Henrik's artwork, the 1.1
   source, and now the placeholder console font. Building privately is fine;
   distribution is not covered by Umoria's GPL relicensing.

## For me
