// Entry point for the graphical build.
//
// Umoria's own main() is left in the submodule untouched. This one does the
// same work, with the frontend options handled before the display opens:
// Umoria calls initscr() with no arguments, so scale and headless mode have
// to be in place by then.
#include <cstdio>
#include <cstring>
#include <string>

#include "amiga_curses.hpp"

// Umoria's headers are C++ but assume they are included as a set.
#include "headers.h"
#include "version.h"

namespace {

const char *kUsage =
    "usage: moria-amiga [OPTIONS] [SAVEGAME]\n"
    "\n"
    "Robert A. Koeneke's Moria, with Henrik Harmsen's Amiga graphics.\n"
    "\n"
    "Frontend options:\n"
    "  --scale N        window is 640*N x 200*N (default: 2)\n"
    "  --fullscreen     start fullscreen\n"
    "  --headless       run without a display, for screenshots and tests\n"
    "  --screenshot F   write the 640x200 screen to F and exit\n"
    "  --keys KEYS      type KEYS into the game, then screenshot and exit.\n"
    "                   \\e is Escape, \\n Return, \\t Tab, \\\\ a backslash\n"
    "\n"
    "Game options:\n"
    "  -n               force start of a new game\n"
    "  -r               roguelike keys\n"
    "  -s NUMBER        game seed\n"
    "  -w               wizard mode\n"
    "  -v               print version and exit\n"
    "  -h, --help       this message\n";

struct Options {
    moria::ui::Options frontend;
    std::string screenshot;
    std::string keys;
    std::string save_game;
    uint32_t seed = 0;
    bool new_game = false;
    bool roguelike_keys = false;
    bool wizard = false;
    bool help = false;
    bool version = false;
    bool bad_usage = false;
};

// Backslash escapes, so a shell can express Escape and Return in --keys.
std::string unescape(const char *text) {
    std::string out;
    for (const char *p = text; *p != '\0'; ++p) {
        if (*p != '\\' || p[1] == '\0') {
            out += *p;
            continue;
        }
        switch (*++p) {
            case 'e': out += '\033'; break;
            case 'n': out += '\n'; break;
            case 'r': out += '\r'; break;
            case 't': out += '\t'; break;
            case '\\': out += '\\'; break;
            default: out += '\\'; out += *p; break;
        }
    }
    return out;
}

bool parse_seed(const char *text, uint32_t &seed) {
    int value = 0;
    if (!stringToNumber(text, value) || value <= 0) {
        return false;
    }
    seed = static_cast<uint32_t>(value);
    return true;
}

Options parse(int argc, char *argv[]) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        const bool has_value = (i + 1) < argc;

        if (arg == "--scale" && has_value) {
            options.frontend.scale = std::atoi(argv[++i]);
        } else if (arg == "--screenshot" && has_value) {
            options.screenshot = argv[++i];
        } else if (arg == "--keys" && has_value) {
            options.keys = unescape(argv[++i]);
        } else if (arg == "--fullscreen") {
            options.frontend.fullscreen = true;
        } else if (arg == "--headless") {
            options.frontend.headless = true;
        } else if (arg == "--help" || arg == "-h") {
            options.help = true;
        } else if (arg == "-v") {
            options.version = true;
        } else if (arg == "-n") {
            options.new_game = true;
        } else if (arg == "-r") {
            options.roguelike_keys = true;
        } else if (arg == "-w") {
            options.wizard = true;
        } else if (arg == "-s" && has_value) {
            if (!parse_seed(argv[++i], options.seed)) {
                std::fprintf(stderr,
                             "game seed must be a decimal number between 1 and "
                             "2147483647\n");
                options.bad_usage = true;
            }
        } else if (!arg.empty() && arg[0] != '-') {
            options.save_game = arg;
        } else {
            std::fprintf(stderr, "unknown option '%s'\n\n%s", arg.c_str(), kUsage);
            options.bad_usage = true;
        }
    }
    return options;
}

}  // namespace

int main(int argc, char *argv[]) {
    const Options options = parse(argc, argv);

    if (options.bad_usage) {
        return 1;
    }
    if (options.help) {
        std::fputs(kUsage, stdout);
        return 0;
    }
    if (options.version) {
        std::printf("moria-amiga, Umoria %d.%d.%d\n", CURRENT_VERSION_MAJOR,
                    CURRENT_VERSION_MINOR, CURRENT_VERSION_PATCH);
        return 0;
    }

    if (!initializeScoreFile()) {
        std::fprintf(stderr, "Can't open score file '%s'\n",
                     config::files::scores.c_str());
        return 1;
    }
    if (!checkFilePermissions()) {
        return 1;
    }

    moria::engine::setFrontendOptions(options.frontend);

    if (!terminalInitialize()) {
        return 1;
    }

    if (!options.save_game.empty()) {
        config::files::save_game = options.save_game;
    }
    if (options.wizard) {
        game.to_be_wizard = true;
    }

    // Driving the real game to a known screen and photographing it. The
    // script runs out, the screen is written, the process exits.
    if (!options.keys.empty()) {
        moria::engine::setScriptedInput(options.keys.c_str(),
                                        options.screenshot.c_str());
        startMoria(options.seed, options.new_game, options.roguelike_keys);
        return 0;
    }

    // A bare --screenshot stops at the first drawn screen, which is enough to
    // prove the display came up.
    if (!options.screenshot.empty()) {
        const bool ok = moria::engine::saveScreenshot(options.screenshot.c_str());
        terminalRestore();
        if (ok) {
            std::printf("wrote %s\n", options.screenshot.c_str());
        }
        return ok ? 0 : 1;
    }

    startMoria(options.seed, options.new_game, options.roguelike_keys);

    return 0;
}
