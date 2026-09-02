// Amiga presentation identity: monster or object -> display code.
//
// Standard Umoria draws whole categories with one letter -- every centipede a
// 'c', every snake a 'J'. Henrik Harmsen gave 96 creatures and 139 objects
// their own graphics by using codes above the printable range, which GFX_CORR
// then maps to individual tiles.
//
// Those codes cannot be written back into `creatures_list[].sprite`, because
// gameplay reads that field: monsters breed by comparing it to 'd' and 'D',
// and the genocide command asks the player for a symbol. So the substitution
// happens here, at the moment a dungeon cell is drawn, keeping the three
// concerns apart:
//
//     monster identity  ->  Amiga presentation identity  ->  sprite position
//
// Takes plain integers rather than Umoria's Coord_t so the frontend never has
// to include the engine's headers.
#pragma once

namespace moria::engine {

// The display code to draw for the dungeon cell at (dungeon_y, dungeon_x),
// given the symbol Umoria wants drawn there. Returns `symbol` unchanged
// unless that cell holds something Henrik drew individually.
unsigned char displayCodeFor(unsigned char symbol, int dungeon_y, int dungeon_x);

// How many codes were recovered, for the tests.
int creatureCodeCount();
int objectCodeCount();

// The code for a named creature or object, or 0 if it has none.
unsigned char creatureCodeByName(const char *name);
unsigned char objectCodeByName(const char *name);

}  // namespace moria::engine
