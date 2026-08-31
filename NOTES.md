# NOTES

## Now

Project: preservation port of Amiga Moria Graphics 1.2 (Henrik Harmsen frontend)
+ UMoria 5.5 engine → SDL3, native macOS + Emscripten/WASM. Full brief supplied
by owner 2026-09-01 (22-section spec; see conversation).

Boundary that governs every decision: **Henrik owns presentation, UMoria owns
gameplay.** No Amiga emulation, no `amiga.c` compiled — it is the spec, not the
source.

First implementation target (before touching UMoria at all): standalone
`amiga-gfx-test` — 1280x400 window, 640x200 render-target framebuffer,
nearest-neighbour scaling, loads the three atlases, title → Space → fake
dungeon drawn via GFX_CORR, numpad movement, fullscreen toggle, Esc quits.

Blocked on: owner supplying the graphics.

## Ideas

- Convert `.iff` → PNG once as a build/tooling step; keep originals under
  `historical-assets/`. Pixel/palette/geometry identical — container change only.
- GFX_CORR as `std::array<Tile,256>`, unmapped entries seeded with random tile
  positions to preserve hallucination behaviour.
- Pixel regression tests (render deterministic states to 640x200 PNGs) are the
  real test suite here, not unit tests.

## Questions

1. Do we have Henrik's original C source, specifically `amiga_corrlist.c`?
   The brief lists 8 example mappings; the full 0-255 table cannot be
   reconstructed without the source. Hardest single blocker.
2. Graphics arriving as raw `.iff` (ILBM) or already-converted PNG?
3. Build/test host: this checkout is Linux (no ninja, no emsdk, no SDL
   installed; cmake 4.4.3, gcc 13.3). macOS `.app` bundle and Universal build
   can only be produced on the owner's Mac. Plan is Linux SDL3 + Emscripten
   here, Mac packaging there — confirm.
4. Font: is there Topaz 8x8 bitmap data available, or do we source/build a
   compatible 8x8 font?
5. Which UMoria base — upstream `dungeons-of-moria/umoria` (5.7.x restoration)
   as the brief says, accepting its deltas from 5.5?

## For me
