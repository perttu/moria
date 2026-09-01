#!/usr/bin/env python3
"""Retarget Umoria's display code at the Amiga frontend.

`vendored/umoria/src/ui_io.cpp` is the only file in Umoria that talks to a
terminal. Everything in it above the drawing calls -- message combining, the
"-more-" prompt, line editing, the confirmation prompts -- is Umoria's own
logic and must keep working exactly as upstream wrote it. So rather than
forking the file, three exact substitutions are applied to a copy at build
time:

  1. include the curses shim instead of curses itself;
  2. route panelPutTile() to the tile atlas -- that call draws one cell of the
     dungeon map, which is precisely where Henrik's putgfx() sat;
  3. replace the select(2)-on-stdin key poll, which has no meaning when input
     arrives as SDL events.

Nothing else changes, and every substitution must match exactly. If upstream
edits any of these, this fails loudly rather than silently producing a game
that draws the dungeon in ASCII or blocks forever waiting on a file
descriptor nobody writes to.

A fourth substitution, in dungeon.cpp, renames dungeonDisplayMap() so that
src/engine/amiga_overview.cpp can supply Henrik's 1:4 tile map in its place.
Renaming rather than replacing keeps the original one line away and makes the
deviation obvious in a diff.

Usage:
    patch_umoria.py --src vendored/umoria/src --out build/generated
"""

import argparse
import sys

UI_IO_SUBSTITUTIONS = [
    (
        "the curses include",
        '#include "curses.h"',
        '#include "amiga_curses.hpp"\n#include "amiga_sprites.hpp"',
    ),
    (
        "panelPutTile, the dungeon map cell",
        """void panelPutTile(char ch, Coord_t coord) {
    // Real coords convert to screen positions
    coord.y -= dg.panel.row_prt;
    coord.x -= dg.panel.col_prt;

    if (mvaddch(coord.y, coord.x, ch) == ERR) {
        abort();
    }
}""",
        """void panelPutTile(char ch, Coord_t coord) {
    // Henrik Harmsen's putgfx() drew exactly here, and the character is a
    // display code rather than a glyph: it selects a tile through GFX_CORR.
    // The substitution happens while the coordinates are still dungeon
    // coordinates, because that is what identifies what is standing there.
    unsigned char code = moria::engine::displayCodeFor(
        static_cast<unsigned char>(ch), coord.y, coord.x);

    // Real coords convert to screen positions
    coord.y -= dg.panel.row_prt;
    coord.x -= dg.panel.col_prt;

    moria::engine::putTile(coord.y, coord.x, code);
}""",
    ),
    (
        "the non-blocking key poll",
        """bool checkForNonBlockingKeyPress(int microseconds) {
#ifdef _WIN32
    (void) microseconds;

    // Ugly non-blocking read...Ugh! -MRC-
    timeout(8);
    int result = getch();
    timeout(-1);

    return result > 0;
#else
    struct timeval tbuf {};
    int ch;
    fd_set smask;

    // Return true if a read on descriptor 1 will not block.
    tbuf.tv_sec = 0;
    tbuf.tv_usec = microseconds;

    FD_ZERO(&smask);
    FD_SET(STDIN_FILENO, &smask);
    if (select(1, &smask, (fd_set *) nullptr, (fd_set *) nullptr, &tbuf) == 1) {
        ch = getch();
        // check for EOF errors here, select sometimes works even when EOF
        if (ch == -1) {
            eof_flag++;
            return false;
        }
        return true;
    }

    return false;
#endif
}""",
        """bool checkForNonBlockingKeyPress(int microseconds) {
    // Input arrives as SDL events, so there is no file descriptor to select
    // on. The contract is unchanged: consume a waiting key if there is one,
    // and say whether there was.
    (void) microseconds;
    return moria::engine::consumePendingKey();
}""",
    ),
]


DUNGEON_SUBSTITUTIONS = [
    (
        "dungeonDisplayMap, replaced by the 1:4 tile map",
        "void dungeonDisplayMap() {",
        "// Renamed by tools/patch_umoria.py. src/engine/amiga_overview.cpp\n"
        "// defines dungeonDisplayMap() to draw Henrik's reduced tile map;\n"
        "// this ASCII original is kept for reference.\n"
        "void dungeonDisplayMapAscii() {",
    ),
]

FILES = {
    "ui_io.cpp": ("ui_io.amiga.cpp", UI_IO_SUBSTITUTIONS),
    "dungeon.cpp": ("dungeon.amiga.cpp", DUNGEON_SUBSTITUTIONS),
}


def patch(source, substitutions):
    for name, old, new in substitutions:
        if source.count(old) != 1:
            raise SystemExit(
                "patch_umoria.py: could not find exactly one match for %s "
                "(found %d).\n"
                "Upstream has moved. Re-read the file and update the "
                "substitution before this build can be trusted."
                % (name, source.count(old)))
        source = source.replace(old, new)
    return source


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="Umoria's src directory")
    ap.add_argument("--out", required=True, help="directory to write the copies to")
    args = ap.parse_args(argv)

    for filename, (output, substitutions) in sorted(FILES.items()):
        with open("%s/%s" % (args.src, filename), "r") as fh:
            source = fh.read()

        header = ("// Generated by tools/patch_umoria.py from Umoria's %s.\n"
                  "// Substitutions retarget it at the Amiga frontend; see that\n"
                  "// script for what they are and why. Do not edit.\n" % filename)

        with open("%s/%s" % (args.out, output), "w") as fh:
            fh.write(header + patch(source, substitutions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
