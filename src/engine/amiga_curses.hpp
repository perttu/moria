// A curses-shaped shim over the Amiga frontend.
//
// Umoria's terminal layer talks to curses, and only to curses: `move`,
// `addch`, `clrtoeol` and about twenty more, all listed below. Providing
// those over the 640x200 SDL screen means Umoria's own ui_io.cpp keeps its
// logic -- message combining, the "-more-" prompt, line editing -- exactly as
// upstream wrote it, and only the drawing underneath changes.
//
// The names are curses' names, in the global namespace, because that is what
// the code calling them expects. Nothing here talks to a terminal.
#pragma once

#include <cstdint>

#include "ui.hpp"

// Umoria checks these before it will start.
extern int LINES;
extern int COLS;

constexpr int ERR = -1;
constexpr int OK = 0;

// One screen's worth of characters. `newwin` hands back a spare for
// terminalSaveScreen(), which is the only windowing Umoria does.
struct WINDOW {
    struct Cell {
        unsigned char ch = ' ';
        bool is_tile = false;
        moria::ui::Color colour = moria::ui::Color::Normal;
    };

    static constexpr int kRows = 25;   // 200 / 8
    static constexpr int kCols = 80;   // 640 / 8

    Cell cells[kRows][kCols];
    int cursor_row = 0;
    int cursor_col = 0;
};

extern WINDOW *stdscr;
extern WINDOW *curscr;

// Lifecycle
WINDOW *initscr();
int endwin();
WINDOW *newwin(int rows, int cols, int begin_y, int begin_x);
int overwrite(WINDOW *source, WINDOW *destination);
int touchwin(WINDOW *window);

// Terminal modes Umoria asks for. None of them mean anything here, but the
// calls have to exist for its initialization to compile and run unchanged.
int raw();
int noecho();
int nonl();
int keypad(WINDOW *window, bool enable);
int set_escdelay(int milliseconds);
int timeout(int delay);
int mvcur(int old_y, int old_x, int new_y, int new_x);

// Drawing
int move(int row, int col);
int addch(char ch);
int mvaddch(int row, int col, char ch);
int addstr(const char *str);
int mvaddstr(int row, int col, const char *str);
int clrtoeol();
int clrtobot();
int clear();
int refresh();
int wrefresh(WINDOW *window);

// Input
int getch();

#define getyx(window, y, x) ((y) = (window)->cursor_row, (x) = (window)->cursor_col)

namespace moria::engine {

// The one call that is not curses-shaped. panelPutTile() in Umoria's terminal
// layer draws a cell of the dungeon map, which is where Henrik's putgfx() sat,
// so it is routed to the tile atlas rather than to the font.
void putTile(int row, int col, unsigned char display_code);

// The reduced 1:4 overview. These cells are not on the character grid -- they
// are two pixels square, off the 8-pixel lattice entirely -- so they are kept
// as their own layer and drawn over the text. clearScreen() discards them.
void putOverviewTile(int map_x, int map_y, unsigned char display_code);

// Window scale, fullscreen and headless mode, applied when initscr() opens
// the display. Umoria's own startup path calls initscr() with no arguments,
// so these are set beforehand from the command line.
void setFrontendOptions(const ui::Options &options);

// Colour for everything written from here until it is set again. Umoria has
// no notion of colour, so this is driven from the presentation side.
void setColour(ui::Color colour);
ui::Color currentColour();

// Writes the 640x200 screen as composed. Used by the screenshot tests.
bool saveScreenshot(const char *path);

// Test hook. Keys are handed to the game as if typed, in order. When they run
// out, the screen is written to `screenshot_path` (if one was given) and the
// process exits, so a test can drive the real game to a known screen and look
// at it without a human at the keyboard.
void setScriptedInput(const char *keys, const char *screenshot_path);

// True once initscr() has run, so shutdown paths know whether to tear the
// frontend down.
bool isRunning();

// Non-blocking: returns true if a key was waiting, and consumes it.
bool consumePendingKey();

}  // namespace moria::engine
