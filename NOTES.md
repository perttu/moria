# NOTES

## Now

Project: preservation port of Amiga Moria Graphics 1.2 (Henrik Harmsen frontend)
+ UMoria engine → SDL3, native macOS + Emscripten/WASM. Full brief supplied by
owner 2026-09-01 (22-section spec; see conversation).

Boundary that governs every decision: **Henrik owns presentation, UMoria owns
gameplay.** No Amiga emulation, no `amiga.c` compiled — it is the spec, not the
source.

Owner supplied 2026-09-01 (uploads, not yet in-repo — owner must "Add to
project" before we vendor them):

- `source.zip` → Amiga Moria Graphics **1.1** full C source (UMoria 5.4 base),
  57 files, incl. `amiga.c`, `amiga.h`, `amiga_corrlist.c`, `amiga_menu.c`,
  `fastcp.s`, `fastlineclear.s`, `README.amiga` (dated 1992-05-15).
- `Moria.zip` → **1.2** binary distribution: the three `.iff` atlases, the
  680K `Moria` executable, `Docs/` (Amiga.doc, New_Features.doc, Update.doc,
  Moria.doc), `.hlp` files. `news` confirms "Amiga graphics 'Umoria 5.5' V1.2".

Verified from the uploads:

- `init_GFX_CORR()` present in full: **231 distinct display codes** explicitly
  assigned, including the complete extended 128–255 block. Spot checks match
  the brief exactly — `'@'`=(10,2), `'.'`=(20,1), `'#'`=(13,2).
- Hallucination hack confirmed at the top of `init_GFX_CORR()`: all 256 entries
  first seeded with `cx=randint(33)-1`, `cy=randint(7)-1`, then
  `if ((cx<20) && (cx>13)) cx -= 6;`. Preserve verbatim.
- Atlas geometry (ILBM BMHD):
  - `moria_gfx.iff` 320×56, 4 planes, 16 colours, compressed → 40×7 tiles of 8×8
  - `moria_gfxsmall.iff` 80×14, 4 planes → 40×7 cells of 2×2 (the 1:4 map)
  - `moria_title.iff` 640×200, 4 planes, page 640×200 — full-screen title
- Palette: `moria_gfx.iff` CMAP is identical to `ColourTable[16]` in `amiga.c`
  (0x0DCA → #D0C0A0 etc). One authoritative 16-colour palette:
  `#000000 #D0C0A0 #804030 #808080 #C08060 #E0B000 #80F050 #008000
   #004000 #303020 #00A0F0 #000070 #0000F0 #800000 #505050 #F02020`
- `static UBYTE screen[66][22]` in `amiga.c` confirms the 66×22 viewport.
- Small map draws at `x_off = 122` (`amiga.c:1094`), 4 bitplanes unrolled.

First implementation target (before touching UMoria at all): standalone
`amiga-gfx-test` — 1280x400 window, 640x200 render-target framebuffer,
nearest-neighbour scaling, loads the three atlases, title → Space → fake
dungeon drawn via GFX_CORR, numpad movement, fullscreen toggle, Esc quits.

## Ideas

- Convert `.iff` → PNG once as a build/tooling step; keep originals under
  `historical-assets/`. Pixel/palette/geometry identical — container change only.
  ILBM here is byte-run compressed (`comp=1`), 4 interleaved bitplanes.
- GFX_CORR as `std::array<Tile,256>`, seeded exactly as above before the 231
  explicit assignments, so hallucination keeps showing graphics.
- Pixel regression tests (render deterministic states to 640x200 PNGs) are the
  real test suite here, not unit tests.

## Questions

1. ~~Do we have `amiga_corrlist.c`?~~ Resolved 2026-09-01 — full table present.
2. ~~IFF or PNG?~~ Resolved — raw ILBM; we write the converter.
3. Build/test host: this checkout is Linux (no ninja, no emsdk, no SDL
   installed; cmake 4.4.3, gcc 13.3). macOS `.app` bundle and Universal build
   can only be produced on the owner's Mac. Plan is Linux SDL3 + Emscripten
   here, Mac packaging there — confirm.
4. Font: still open. `amiga.c` renders text through the Amiga ROM Topaz font,
   so no glyph data ships in either archive. Either source an open 8x8 Topaz
   reimplementation, or the owner extracts Topaz from a Kickstart ROM they own
   (pixel-exact, owner-side).
5. Which UMoria base — upstream `dungeons-of-moria/umoria` (5.7.x restoration)
   as the brief says, accepting its deltas from the 5.5 the 1.2 assets target?
6. Uploads live outside the repo. Owner needs to "Add to project" for
   `historical-amiga/` and `historical-assets/` to be vendored.

## For me
