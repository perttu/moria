// The reduced 1:4 overview map, as the Amiga drew it.
//
// Umoria shrinks the dungeon by picking the highest-priority character in
// each 3x3 block and printing the result as text. Henrik did something else
// entirely: he drew *every* cell of the 198x66 dungeon as a two-pixel square
// taken from a second atlas, moria_gfxsmall.iff, at x_off = 122, y_off = 34.
// Two pixels instead of eight is the "reduced four times" the documentation
// describes, and it fits the whole dungeon on one 640x200 screen with no
// information thrown away.
//
// Umoria's own dungeonDisplayMap() is renamed rather than deleted -- see
// tools/patch_umoria.py -- so the ASCII version is still there to compare
// against, and this definition takes its place.
#include "amiga_curses.hpp"
#include "amiga_sprites.hpp"
#include "headers.h"
#include "ui.hpp"

// The renamed original, kept for reference and to keep the compiler honest
// about the substitution having happened.
extern void dungeonDisplayMapAscii();

void dungeonDisplayMap() {
    terminalSaveScreen();
    clearScreen();

    for (int y = 0; y < dg.height; ++y) {
        for (int x = 0; x < dg.width; ++x) {
            const char symbol = caveGetTileSymbol(Coord_t{y, x});
            if (symbol == ' ') {
                continue;
            }
            // The same presentation identity the full-size map uses, so a
            // creature Henrik drew individually is individual here too.
            const unsigned char code = moria::engine::displayCodeFor(
                static_cast<unsigned char>(symbol), y, x);
            moria::engine::putOverviewTile(x, y, code);
        }
    }

    putString("Hit any key to continue", Coord_t{23, 23});
    (void) getKeyInput();

    terminalRestoreScreen();
}
