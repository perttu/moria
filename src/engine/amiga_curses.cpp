#include "amiga_curses.hpp"

#include "amiga_colours.hpp"
#include "amiga_web.hpp"

#include <cstdio>   // EOF, which getKeyInput() checks for
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace {

WINDOW g_stdscr;
WINDOW g_curscr;
WINDOW g_spare;

bool g_running = false;
bool g_dirty = true;
moria::ui::Color g_colour = moria::ui::Color::Normal;
moria::ui::Options g_options;

struct OverviewCell {
    int x;
    int y;
    unsigned char code;
};
std::vector<OverviewCell> g_overview;

std::string g_script;
std::string g_script_screenshot;
std::size_t g_script_position = 0;

bool in_bounds(int row, int col) {
    return row >= 0 && col >= 0 && row < WINDOW::kRows && col < WINDOW::kCols;
}

void write_cell(int row, int col, unsigned char ch, bool is_tile) {
    if (!in_bounds(row, col)) {
        return;
    }
    WINDOW::Cell &cell = stdscr->cells[row][col];
    cell.ch = ch;
    cell.is_tile = is_tile;
    cell.colour = g_colour;
    g_dirty = true;
}

// Translate one key event into the byte Umoria expects. The direction digits
// arrive already mapped by the frontend, so Shift+numpad running and
// Ctrl+numpad tunnelling reach the game as the modifier plus the digit, as
// they did on the Amiga.
int translate(const moria::ui::KeyEvent &key) {
    if (key.key == moria::ui::kKeyQuit) {
        return EOF;
    }
    if (key.ctrl && key.key >= '@' && key.key <= '~') {
        return key.key & 0x1F;  // CTRL_KEY()
    }
    return key.key;
}

}  // namespace

int LINES = 24;
int COLS = WINDOW::kCols;

WINDOW *stdscr = &g_stdscr;
WINDOW *curscr = &g_curscr;

WINDOW *initscr() {
    g_options.title = "Moria Amiga";
    if (!moria::ui::init(g_options)) {
        return nullptr;
    }
    g_running = true;
    clear();
    return stdscr;
}

int endwin() {
    // exitProgram() calls terminalRestore() -> here, after saveGame(), so this
    // is where a browser save reaches IndexedDB.
    moria::engine::webFlushSaves();
    if (g_running) {
        moria::ui::shutdown();
        g_running = false;
    }
    return OK;
}

WINDOW *newwin(int, int, int, int) {
    return &g_spare;
}

int overwrite(WINDOW *source, WINDOW *destination) {
    if (source == nullptr || destination == nullptr) {
        return ERR;
    }
    std::memcpy(destination->cells, source->cells, sizeof(source->cells));
    destination->cursor_row = source->cursor_row;
    destination->cursor_col = source->cursor_col;
    g_dirty = true;
    return OK;
}

int touchwin(WINDOW *) {
    g_dirty = true;
    return OK;
}

int raw() { return OK; }
int noecho() { return OK; }
int nonl() { return OK; }
int keypad(WINDOW *, bool) { return OK; }
int set_escdelay(int) { return OK; }
int timeout(int) { return OK; }
int mvcur(int, int, int, int) { return OK; }

int move(int row, int col) {
    if (!in_bounds(row, col)) {
        return ERR;
    }
    stdscr->cursor_row = row;
    stdscr->cursor_col = col;
    return OK;
}

int addch(char ch) {
    write_cell(stdscr->cursor_row, stdscr->cursor_col,
               static_cast<unsigned char>(ch), false);
    if (stdscr->cursor_col + 1 < WINDOW::kCols) {
        stdscr->cursor_col++;
    }
    return OK;
}

int mvaddch(int row, int col, char ch) {
    if (move(row, col) == ERR) {
        return ERR;
    }
    return addch(ch);
}

int addstr(const char *str) {
    if (str == nullptr) {
        return ERR;
    }

    // Umoria has no notion of colour, so it is decided here, from where the
    // text is going and what it says. A whole string at a time: the policy
    // needs the message, not one character of it.
    const moria::ui::Color saved = g_colour;
    g_colour = moria::engine::colours::forText(stdscr->cursor_row,
                                               stdscr->cursor_col, str);

    for (const char *p = str; *p != '\0'; ++p) {
        addch(*p);
    }

    g_colour = saved;
    return OK;
}

int mvaddstr(int row, int col, const char *str) {
    if (move(row, col) == ERR) {
        return ERR;
    }
    return addstr(str);
}

int clrtoeol() {
    for (int col = stdscr->cursor_col; col < WINDOW::kCols; ++col) {
        write_cell(stdscr->cursor_row, col, ' ', false);
    }
    return OK;
}

int clrtobot() {
    clrtoeol();
    for (int row = stdscr->cursor_row + 1; row < WINDOW::kRows; ++row) {
        for (int col = 0; col < WINDOW::kCols; ++col) {
            write_cell(row, col, ' ', false);
        }
    }
    return OK;
}

int clear() {
    for (int row = 0; row < WINDOW::kRows; ++row) {
        for (int col = 0; col < WINDOW::kCols; ++col) {
            WINDOW::Cell &cell = stdscr->cells[row][col];
            cell.ch = ' ';
            cell.is_tile = false;
            cell.colour = moria::ui::Color::Normal;
        }
    }
    stdscr->cursor_row = 0;
    stdscr->cursor_col = 0;
    g_overview.clear();
    g_dirty = true;
    return OK;
}

int refresh() {
    if (!g_running) {
        return ERR;
    }
    if (!g_dirty) {
        moria::ui::present();
        return OK;
    }

    moria::ui::clear();
    for (int row = 0; row < WINDOW::kRows; ++row) {
        for (int col = 0; col < WINDOW::kCols; ++col) {
            const WINDOW::Cell &cell = stdscr->cells[row][col];
            if (cell.is_tile) {
                moria::ui::tile(col, row, cell.ch);
            } else if (cell.ch != ' ') {
                const char text[2] = {static_cast<char>(cell.ch), '\0'};
                moria::ui::text(col, row, text, cell.colour);
            }
        }
    }

    // The reduced map sits on top, on its own two-pixel lattice.
    for (const OverviewCell &cell : g_overview) {
        moria::ui::overview_tile(cell.x, cell.y, cell.code);
    }

    moria::ui::present();
    g_dirty = false;
    return OK;
}

int wrefresh(WINDOW *) {
    g_dirty = true;
    return refresh();
}

int getch() {
    refresh();

    if (g_script_position < g_script.size()) {
        return static_cast<unsigned char>(g_script[g_script_position++]);
    }
    if (!g_script.empty() && !g_script_screenshot.empty()) {
        // The script has run out: capture what the game drew and stop. This
        // is how the pixel tests look at real game screens.
        moria::ui::save_screenshot(g_script_screenshot.c_str());
        std::printf("wrote %s\n", g_script_screenshot.c_str());
        std::fflush(stdout);
        moria::ui::shutdown();
        std::exit(0);
    }

    const moria::ui::KeyEvent key = moria::ui::get_key();
    return translate(key);
}

namespace moria::engine {

void putTile(int row, int col, unsigned char display_code) {
    write_cell(row, col, display_code, true);
}

void putOverviewTile(int map_x, int map_y, unsigned char display_code) {
    g_overview.push_back(OverviewCell{map_x, map_y, display_code});
    g_dirty = true;
}

void setFrontendOptions(const ui::Options &options) {
    g_options = options;
}

void setScriptedInput(const char *keys, const char *screenshot_path) {
    g_script = (keys != nullptr) ? keys : "";
    g_script_screenshot = (screenshot_path != nullptr) ? screenshot_path : "";
    g_script_position = 0;
}

void setColour(ui::Color colour) {
    g_colour = colour;
}

bool saveScreenshot(const char *path) {
    refresh();
    return ui::save_screenshot(path);
}

ui::Color currentColour() {
    return g_colour;
}

bool isRunning() {
    return g_running;
}

bool consumePendingKey() {
    if (!g_running) {
        return false;
    }
    const ui::KeyEvent key = ui::poll_key();
    return key.key != ui::kKeyNone;
}

}  // namespace moria::engine
