// The narrow display API the game talks to.
//
// SDL knows about windows, keyboards, textures and scaling. Moria knows
// nothing about macOS, Linux or browsers. Everything platform-shaped lives
// behind this header; nothing above it may include an SDL header.
#pragma once

#include <cstdint>

namespace moria::ui {

// The Amiga original is a fixed 640x200 screen on an 8-pixel grid. This is a
// virtual screen, never a window size: it is rendered at 1:1 and then scaled.
inline constexpr int kScreenWidth = 640;
inline constexpr int kScreenHeight = 200;
inline constexpr int kCellSize = 8;
inline constexpr int kCols = kScreenWidth / kCellSize;   // 80
inline constexpr int kRows = kScreenHeight / kCellSize;  // 25

// Dungeon viewport. amiga.c indexes `static UBYTE screen[66][22]` as
// screen[col - 13][row - 1], which fixes both the size and the origin:
// row 0 is the message line, columns 0..12 are the stat sidebar.
inline constexpr int kMapColOffset = 13;
inline constexpr int kMapRowOffset = 1;
inline constexpr int kMapCols = 66;
inline constexpr int kMapRows = 22;

// Reduced 1:4 overview: amiga.c sets x_off = 122, y_off = 34 and steps two
// pixels per dungeon cell, drawing from the separate small atlas.
inline constexpr int kOverviewX = 122;
inline constexpr int kOverviewY = 34;
inline constexpr int kOverviewCell = 2;

// Semantic message colours described in Amiga.doc. Mapped to the original
// 16-entry palette in amiga_palette.hpp rather than to literal RGB here.
enum class Color {
    Normal,
    Danger,
    Warning,
    Success,
    Kill,
    StatLoss,
    StatGain,
    Good,
};

struct Options {
    int scale = 2;            // window is 640*scale x 200*scale
    bool fullscreen = false;
    bool headless = false;    // dummy video driver + software renderer
    const char *title = "Moria Amiga";
};

// Special keys returned by get_key(). Printable input is returned as its own
// ASCII value, so these start above the ASCII range.
enum Key : int {
    kKeyNone = 0,
    kKeyQuit = -1,
    kKeyEscape = 27,
    kKeyEnter = 13,
    kKeyBackspace = 8,
};

struct KeyEvent {
    int key = kKeyNone;
    bool shift = false;
    bool ctrl = false;
    bool alt = false;
    bool gui = false;  // Command on macOS
};

// Exposed for tests: the byte Moria receives for a raw key press. Takes
// plain integers so nothing above this header needs SDL's types.
int translate_key_press(int scancode, unsigned int modifiers);

bool init(const Options &options);
void shutdown();

void clear();
void present();

void text(int col, int row, const char *str, Color colour = Color::Normal);
void tile(int col, int row, std::uint8_t display_code);

// Draws one cell of the reduced map, in overview pixel coordinates.
void overview_tile(int map_x, int map_y, std::uint8_t display_code);

void show_title();

KeyEvent get_key();   // blocks until a key arrives or the window closes
KeyEvent poll_key();  // returns kKeyNone when nothing is waiting

void toggle_fullscreen();

// Yields for roughly this long. Native builds use it to idle between turns;
// the browser build never calls it, because there the browser owns the loop.
void delay(unsigned milliseconds);

// Writes the 640x200 virtual screen exactly as composed, before scaling.
// This is the hook the pixel regression tests hang off.
bool save_screenshot(const char *path);

}  // namespace moria::ui
