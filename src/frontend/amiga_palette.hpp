// Henrik Harmsen's 16-colour palette, and the semantic colours on top of it.
#pragma once

#include <cstdint>

#include "ui.hpp"

namespace moria::gfx {

struct Rgb {
    std::uint8_t r, g, b;
};

// ColourTable[16] in amiga.c, as Amiga 12-bit values expanded to 8 bits per
// channel. Identical to the CMAP chunk of moria_gfx.iff, so the tiles and the
// text share one palette.
inline constexpr Rgb kPalette[16] = {
    {0x00, 0x00, 0x00},  //  0  0x0000  black
    {0xD0, 0xC0, 0xA0},  //  1  0x0DCA  bone white -- normal text
    {0x80, 0x40, 0x30},  //  2  0x0843  brown
    {0x80, 0x80, 0x80},  //  3  0x0888  grey
    {0xC0, 0x80, 0x60},  //  4  0x0C86  light brown
    {0xE0, 0xB0, 0x00},  //  5  0x0EB0  yellow
    {0x80, 0xF0, 0x50},  //  6  0x08F5  light green
    {0x00, 0x80, 0x00},  //  7  0x0080  green
    {0x00, 0x40, 0x00},  //  8  0x0040  dark green
    {0x30, 0x30, 0x20},  //  9  0x0332  dark olive
    {0x00, 0xA0, 0xF0},  // 10  0x00AF  light blue
    {0x00, 0x00, 0x70},  // 11  0x0007  dark blue
    {0x00, 0x00, 0xF0},  // 12  0x000F  blue
    {0x80, 0x00, 0x00},  // 13  0x0800  dark red
    {0x50, 0x50, 0x50},  // 14  0x0555  dark grey
    {0xF0, 0x20, 0x20},  // 15  0x0F22  red
};

// Amiga.doc describes the message colours by name: white for normal
// information, red for danger, yellow for warnings, green for successful
// hits, light blue for kills, dark red for stat loss, blue for stat gain.
//
// Index 1 for Color::Normal is confirmed from the source -- io.c passes a
// literal 1 for the uncoloured " -more-" prompt. The rest are matched by
// name against the palette above and still want checking against their call
// sites once the engine is wired up; the game passes bare palette indices,
// with no named constants to grep for.
inline constexpr std::uint8_t palette_index(ui::Color colour) {
    switch (colour) {
        case ui::Color::Normal:   return 1;   // bone white
        case ui::Color::Danger:   return 15;  // red
        case ui::Color::Warning:  return 5;   // yellow
        case ui::Color::Success:  return 6;   // light green
        case ui::Color::Kill:     return 10;  // light blue
        case ui::Color::StatLoss: return 13;  // dark red
        case ui::Color::StatGain: return 12;  // blue
        case ui::Color::Good:     return 7;   // green
    }
    return 1;
}

inline constexpr Rgb rgb(ui::Color colour) {
    return kPalette[palette_index(colour)];
}

}  // namespace moria::gfx
