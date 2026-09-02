// Display code -> tile atlas cell, following Henrik Harmsen's GFX_CORR table.
//
// Three concerns stay separate here: monster identity, Amiga presentation
// identity (the display code), and sprite coordinates. The game engine only
// ever produces a display code; it never learns where a sprite lives.
#pragma once

#include <array>
#include <cstdint>

namespace moria::gfx {

struct Tile {
    std::uint8_t x;  // column in the atlas, in 8-pixel cells
    std::uint8_t y;  // row in the atlas, in 8-pixel cells
};

// Builds the full 0..255 table the way init_GFX_CORR() does: seed every entry
// with a random atlas position first, then apply the explicit assignments.
//
// The seeding is deliberate, not sloppy. It is what keeps hallucination
// showing graphics instead of dropping to ASCII for unmapped codes, and it is
// preserved rather than tidied away. `seed` selects the random sequence; the
// original drew from Moria's own generator, so any sequence is faithful in
// behaviour, and a fixed seed keeps screenshot tests reproducible.
std::array<Tile, 256> build_table(std::uint32_t seed);

// The table the renderer uses. Built once, from a fixed seed, so that a
// screenshot of the same game state is the same image every time.
const std::array<Tile, 256> &tiles();

// The atlas cell for one display code.
Tile tile_for(std::uint8_t display_code);

// True when the code was explicitly mapped by Henrik rather than seeded.
bool is_explicit(std::uint8_t display_code);

// How many codes init_GFX_CORR() assigns explicitly.
int explicit_count();

}  // namespace moria::gfx
