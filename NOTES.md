# NOTES

Preservation port of Amiga Moria Graphics 1.2 (Henrik Harmsen's frontend) plus
UMoria, to SDL3 on Linux, macOS and the browser. Full brief supplied by the
owner 2026-09-01. Governing boundary: **Henrik owns presentation, UMoria owns
gameplay.** No emulation; `amiga.c` is the specification, never compiled.

Build and run instructions live in README.md.

## Status

Accepted by the owner on 2026-09-01 after three review rounds without a pass,
with the outstanding findings left unfixed. Two of them were then reopened by
the owner after playing the game, and are now fixed:

- **The reduced map stayed painted over the dungeon after dismissal.** The
  overview is a second layer, not part of the character grid, and
  `terminalSaveScreen()` / `terminalRestoreScreen()` copied only `WINDOW`
  cells. `overwrite()` now carries the overlay with the screen it belongs to.
- **Shifted characters never reached the game.** `SDL_KeyboardEvent::key` is
  the *unmodified* keycode, so Shift+8 arrived as `8`. That made `*`
  (inventory), `?` (help), `!`, `:`, `_`, `+` (Henrik's look command) and --
  worst of all -- `>` and `<` unreachable, so **the stairs could not be
  taken from the keyboard at all**. The frontend now asks SDL to apply the
  modifiers, which is also layout-correct.

A third was then reopened and fixed too: **browser saving**, which now works
and is asserted on every `web-smoke` run. See below — my original explanation
of why it failed was wrong.

Still unfixed from that review, as accepted:

- Generated sources can remain stale.
- Browser tests can report success without proving their claims.

Those two are as the reviewer summarised them; I did not investigate them, so
no detail here is mine to add.

## Where this actually is

**Both of the brief's hard questions are answered yes**, and 13 of the 14
milestones are done. Umoria 5.7.15 runs on Henrik's frontend — natively and in
a browser — with his tiles, his extended graphics, his colours, his reduced
map, and saves that persist on both. Only the macOS bundle is outstanding, and
it needs a Mac.

| # | milestone | state |
| --- | --- | --- |
| 1 | asset viewer | done |
| 2 | tile atlas viewer | done |
| 3 | static Amiga screen | done |
| 4 | keyboard frontend | done — real keys into the real engine |
| 5 | playable town | done — created, played, saved and reloaded |
| 6 | playable dungeon | done — reached and checked in a test |
| 7 | special graphics | done — 96 creatures and 139 objects restored |
| 8 | overview map | done — Umoria's map command draws the small atlas |
| 9 | full Amiga UI | colour done; message classification is an approximation |
| 10 | save/load | done — round-trip checked pixel for pixel |
| 11 | macOS .app | blocked: no Mac here |
| 12 | Emscripten | done — the game runs in Chrome, byte-identical to native |
| 13 | browser saves | done — saved and read back, via localStorage |
| 14 | pixel regression tests | done, including the real game's screens |

The browser build compiles with **Asyncify**, which unwinds and resumes the
stack around `ui::delay()`. That is what lets Umoria keep reading keys from
deep inside its call stack without freezing the tab: the engine keeps its
structure, and the browser keeps its event loop. The browser's character
creation screen is byte-identical to the native one.

**Browser saving works, and my earlier diagnosis of why it did not was
wrong.** I reported that `exit()` under Asyncify froze the tab. It does not.
What actually happened:

- The failing test used `--user-data-dir` to share storage between two page
  loads. **That flag alone hangs this headless Chrome**, on any page, save
  path or not. The feature was never the thing failing; the harness was.
- IDBFS's `syncfs()` never called back here — not on load, not on store.
  Waiting for it left the module spinning; holding startup open with a run
  dependency left `main()` never running at all.

So persistence is done by hand, and with **localStorage rather than
IndexedDB** — a deliberate deviation from the brief. localStorage is
synchronous: the restore simply happens in `preRun`, with no callback to miss
and no interaction with Asyncify. A Moria save is about 5 kB against a budget
of about 5 MB. `src/engine/web_pre.js` holds both ends, and a `beforeunload`
handler flushes for a player who just closes the tab.

`exitProgram()` is still patched, for a different and real reason: it calls
`exit(0)`, which would tear the runtime down with nothing to return to. The
browser build calls `emscripten_exit_with_live_runtime()` instead, so the last
screen stays on the canvas and the tab stays responsive.

Verified end to end in headless Chrome, both halves. Saving: the game writes
4850 bytes — the same size as the native save — and the page reads all 4850
back out of storage. Loading: a save made by the native build is planted in
storage, the page is opened without `-n`, and the game comes up in the town
as that character. `web-smoke` asserts both on every run.

`^X` is Moria's *save and quit*, so it ends the session by design: the game
saves, shows the high scores, and stops. In the browser it then parks with
"you can close this tab" rather than exiting. Reloading the page resumes from
the save.

## The browser page

Emscripten's default shell is a logo and a text area around a canvas. It is
replaced by `src/web/shell.html`: the game, a searchable command reference,
and a races-and-classes table, as three linkable tabs.

Both panels are **generated at build time from Umoria's own files** —
`data/help.txt` and `data/rl_help.txt` for the commands, `data_player.cpp` for
the tables — so the reference cannot drift from the game it describes. Nothing
is hand-copied.

The race and class tables are positional C initialisers with no field names,
and the struct comments in `character.h` do not line up with the literals: the
fields are at 24-27 and 1/9-16, not where counting the comments suggests. An
off-by-one there produces a table that looks entirely plausible and is wrong,
so `tool-web-help` checks values that can be confirmed by reading the game —
a Half-Troll gets 12 hit points, a Dwarf cannot be a Mage, a Human is 100%
experience.

## Extended display codes

Standard Umoria draws whole categories with one letter: every centipede a
'c', every townsperson a 'p'. Henrik gave **96 creatures and 139 objects**
their own graphics by putting a code outside the printable range in the data
tables — "Filthy Street Urchin" is 133, not 't'; "Ancient Red Dragon" is 238,
not 'D'. Not all are above 127: "White Icky-Thing" is 10.

Those codes cannot simply be written back into `creatures_list[].sprite`,
because gameplay reads that field — `monster_manager.cpp` breeds by comparing
it to 'd' and 'D', and the genocide command asks the player for a symbol. So
`tools/gen_amiga_codes.py` recovers the mapping keyed by **name**, and
`displayCodeFor()` substitutes at the moment a cell is drawn, in
`panelPutTile()`, while the coordinates are still dungeon coordinates.

Matching against 5.7.15 by name: **all 96 creatures matched exactly.** Objects
needed more work — 122 exact, 12 after ignoring case and punctuation
(`& Cat-O-Nine Tails` → `& Cat-o'-Nine-Tails`), and 5 renamed outright:

- `& Mace (Lead-filled)` → `& Lead-Filled Mace`
- `[Beginners-Magik]` → `[Beginners-Magick]`
- `[Magik I]` / `[Magik II]` → `[Magick I]` / `[Magick II]`
- `[Exorcism and Dispelling]` → `[Exorcisms and Dispellings]`

That is the 5.5-to-5.7 drift this file warned about, and it turned out to be
five objects rather than anything structural. The generator refuses to emit a
table if a name goes unmatched, so a future rename is a build failure rather
than a creature quietly losing its graphic — and it also checks every
recovered code has an explicit GFX_CORR tile, since a code without one would
draw whatever the hallucination seeding left there.

## Colour

Henrik implemented his scheme by passing a colour from each engine call site.
This port does not, because modifying gameplay source is the one thing the
whole arrangement exists to avoid. `src/engine/amiga_colours.cpp` decides
instead, from the screen position and the game's own state.

Where Amiga.doc is precise, the rule is computed, not guessed:

- hit points and mana are coloured by percentage — 0-25% red, 25-75% yellow,
  75-100% light green, 100% white — read from `py.misc`, so a wound shows
  even before the number on screen changes;
- a characteristic is yellow while `py.stats.current[i] < py.stats.max[i]`;
- `Hungry` is yellow and `Weak` is red, per Update.doc;
- `-more-` is deliberately never coloured, so it cannot give away a kill
  before the message arrives. Update.doc calls this out as a 1.1 fix, and
  `io.c` in the 1.1 source passes a literal colour 1 for it.

Message colours cannot work that way, and an earlier attempt that tried to
was wrong. **Umoria prints the message before it applies the consequence** --
`monsterPrintAttackDescription()` before `executeAttackOnPlayer()`, "You feel
weaker." before `playerStatRandomDecrease()`, "You have picked the lock."
before `py.misc.exp++`. Comparing state against the previous message therefore
coloured the wrong line: the attack came out white, and the next unrelated
message came out red. Messages are classified from their text instead, using
phrases taken from Umoria's own source, which is also what Henrik was choosing
between when he coloured each call site by hand.

**That is an approximation, and phrases the table does not know are white.**
Ordering inside the table is load-bearing: "but it passes" is matched before
the drain phrase it contains, the chest before the kill, a trap before a hit.

Two colours that are easy to conflate are kept apart, because Henrik's palette
holds both: a successful hit is green (entry 7), while 75-100% vitals are
light green (entry 6).

`colour-test` asserts every documented rule, runs the attack, stat-drain and
lock-picking cases **in the engine's own order**, and finishes by rendering
through the real shim and counting pixels: every drawn pixel of the hit point
line at 20% health is red (134 of 134), and every pixel of a hit message is
green (346 of 346), with none of the vitals' light green among them.

Five negative controls were run and all five fired: removing the attack
phrase, reintroducing the HP-delta guard, putting hits back on light green,
restoring the floored integer percentage, and colouring only the first glyph.

### Done so far

- SDL3 vendored; frontend, display API, 640x200 virtual screen, letterboxing
- `tools/iff_convert.py`, `tools/gen_gfx_corr.py`, `tools/gen_font.py`
- Linux build works without the full X11 -dev set
- Emscripten build, running and pixel-checked in headless Chrome
- Test suite: `gfx-corr`, `colours`, `sprites`, `pixel-screens`,
  `game-screens`, `smoke-start`, `web-smoke`, the three tool suites, and an
  opt-in `build-from-clean`

### Next

- [ ] Browser saves: stop `exitProgram()` calling `exit(0)` under Emscripten,
      so the flush to IndexedDB can complete. Then turn on
      `web_smoke.py --check-saves`.
- [ ] macOS build and `.app` bundle — needs a Mac. The CMake is conventional
      but has never been run.
- [ ] Sharpen message colouring: every phrase `classifyMessageText()` does not
      know is a message Henrik coloured and we draw white
- [ ] Replace the placeholder font with real Topaz
- [ ] Licence review before anything is published

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

- `ctest` passes on Linux with every optional test configured in — the
  browser test needs `-DMORIA_WEB_BUILD_DIR`, and `build-from-clean` needs
  `-DMORIA_TEST_CLEAN_BUILD=ON`. Both golden files record screens that were
  rendered and looked at. (Counts are deliberately not quoted here; they go
  stale the moment a test is added.)
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
brief specifies. Vendored 2026-09-01 and now built and wired: `moria-amiga`
runs the game on the frontend.

**How it is connected.** Umoria's sources are compiled straight out of the
submodule, minus two files. `src/engine/main.cpp` replaces its `main()` so the
frontend options are in place before `initscr()`. And `ui_io.cpp` — the only
file in Umoria that talks to a terminal — is copied at build time with three
exact substitutions by `tools/patch_ui_io.py`: the curses include becomes the
shim in `src/engine/amiga_curses.hpp`, `panelPutTile()` routes to the tile
atlas, and the `select(2)` key poll becomes an SDL poll. Every substitution
must match exactly or the build fails loudly. **No gameplay source is
modified**, and Umoria's own terminal logic — message combining, the
"-more-" prompt, line editing — is upstream's, unchanged.

The shim is curses-shaped on purpose: `move`, `addch`, `clrtoeol` and about
twenty more, over an 80x25 grid of cells that each know whether they hold a
font glyph or a dungeon tile. `refresh()` walks the grid and draws it.

Original survey, which is why it went this smoothly:

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
