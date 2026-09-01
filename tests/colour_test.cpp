// Assertions on Henrik Harmsen's colour scheme.
//
// The values here are quoted from Amiga.doc and Update.doc, not chosen. A
// screenshot cannot check most of them: an undamaged character at full health
// with no drained stats is correctly drawn entirely in white, so the rules
// only become visible in states that are awkward to reach by playing.
#include <cstdio>
#include <cstring>

#include "amiga_colours.hpp"
#include "amiga_curses.hpp"
#include "amiga_palette.hpp"
#include "headers.h"

namespace {

using moria::ui::Color;

int g_failures = 0;

const char *name(Color colour) {
    switch (colour) {
        case Color::Normal: return "Normal (white)";
        case Color::Danger: return "Danger (red)";
        case Color::Warning: return "Warning (yellow)";
        case Color::Success: return "Success (light green)";
        case Color::Kill: return "Kill (light blue)";
        case Color::StatLoss: return "StatLoss (dark red)";
        case Color::StatGain: return "StatGain (blue)";
        case Color::Good: return "Good (green)";
    }
    return "?";
}

void expect(const char *what, Color got, Color want) {
    if (got == want) {
        std::printf("ok   %-52s %s\n", what, name(want));
        return;
    }
    std::printf("FAIL %-52s expected %s, got %s\n", what, name(want), name(got));
    ++g_failures;
}

void expectTrue(const char *what, bool condition) {
    if (condition) {
        std::printf("ok   %s\n", what);
    } else {
        std::printf("FAIL %s\n", what);
        ++g_failures;
    }
}

// Rows from Umoria's src/ui.cpp.
constexpr int kMessageRow = 0;
constexpr int kStrRow = 6;
constexpr int kManaRow = 15;
constexpr int kCurrentHpRow = 17;
constexpr int kStatusRow = 23;
constexpr int kMapColumn = 13;

void setHitPoints(int current, int maximum) {
    py.misc.current_hp = static_cast<int16_t>(current);
    py.misc.max_hp = static_cast<int16_t>(maximum);
}

void resetPlayer() {
    game.character_generated = true;
    setHitPoints(100, 100);
    py.misc.current_mana = 100;
    py.misc.mana = 100;
    py.misc.exp = 0;
    for (int i = 0; i < 6; ++i) {
        py.stats.current[i] = 18;
        py.stats.max[i] = 18;
    }
    // Two messages: the first only takes the baseline snapshot.
    (void) moria::engine::colours::forText(kMessageRow, 0, "settling in");
    (void) moria::engine::colours::forText(kMessageRow, 0, "settling in");
}

Color message(const char *text) {
    return moria::engine::colours::forText(kMessageRow, 0, text);
}

// Counts pixels of one colour on one text row of the saved screen.
// save_screenshot() writes an uncompressed 24-bit bottom-up BMP.
int countPixels(const char *path, int text_row, moria::gfx::Rgb wanted) {
    FILE *file = fopen(path, "rb");
    if (file == nullptr) {
        return -1;
    }

    unsigned char header[54];
    if (fread(header, 1, sizeof(header), file) != sizeof(header)) {
        fclose(file);
        return -1;
    }
    const int width = *reinterpret_cast<int *>(header + 18);
    const int height = *reinterpret_cast<int *>(header + 22);
    const int offset = *reinterpret_cast<int *>(header + 10);
    const int stride = ((width * 3) + 3) & ~3;

    int found = 0;
    for (int line = 0; line < 8; ++line) {
        const int y = text_row * 8 + line;
        const int source_row = height - 1 - y;  // bottom-up
        if (fseek(file, offset + source_row * stride, SEEK_SET) != 0) {
            break;
        }
        for (int x = 0; x < width; ++x) {
            unsigned char bgr[3];
            if (fread(bgr, 1, 3, file) != 3) {
                break;
            }
            if (bgr[2] == wanted.r && bgr[1] == wanted.g && bgr[0] == wanted.b) {
                ++found;
            }
        }
    }

    fclose(file);
    return found;
}

}  // namespace

int main() {
    resetPlayer();

    // --- Amiga.doc: "when hitpoints or mana is between 0-25% it will be red,
    // 25%-75% in yellow, 75%-100% in light green and 100% in white."
    setHitPoints(100, 100);
    expect("hit points at 100%", moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"),
           Color::Normal);
    setHitPoints(80, 100);
    expect("hit points at 80%", moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"),
           Color::Success);
    setHitPoints(50, 100);
    expect("hit points at 50%", moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"),
           Color::Warning);
    setHitPoints(25, 100);
    expect("hit points at exactly 25%", moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"),
           Color::Danger);
    setHitPoints(1, 100);
    expect("hit points at 1%", moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"),
           Color::Danger);
    setHitPoints(100, 100);

    py.misc.current_mana = 10;
    py.misc.mana = 100;
    expect("mana at 10%", moria::engine::colours::forText(kManaRow, 0, "MANA"),
           Color::Danger);
    py.misc.current_mana = 0;
    py.misc.mana = 0;
    expect("no mana at all, as a warrior has",
           moria::engine::colours::forText(kManaRow, 0, "MANA"), Color::Normal);
    py.misc.current_mana = 100;
    py.misc.mana = 100;

    // --- Amiga.doc: "when some status has decreased, it will be displayed in
    // yellow."
    expect("an undrained characteristic",
           moria::engine::colours::forText(kStrRow, 0, "STR"), Color::Normal);
    py.stats.current[0] = 16;
    py.stats.max[0] = 18;
    expect("a drained characteristic",
           moria::engine::colours::forText(kStrRow, 0, "STR"), Color::Warning);
    py.stats.current[0] = 18;

    // --- Update.doc: "when you get hungry, the 'Hungry' - message in the stat
    // block is now yellow, and when you get 'Weak' it is displayed in red."
    expect("the Hungry indicator",
           moria::engine::colours::forText(kStatusRow, 0, "Hungry"), Color::Warning);
    expect("the Weak indicator",
           moria::engine::colours::forText(kStatusRow, 0, "Weak  "), Color::Danger);

    // --- Amiga.doc's message colours. The stat and wound cases are decided
    // from the game's state, not from the words.
    resetPlayer();
    py.stats.current[2] = 15;  // wisdom drained since the last message
    expect("a message printed as a stat drops", message("You feel very naive."),
           Color::StatLoss);

    resetPlayer();
    py.stats.current[3] = 19;  // dexterity raised since the last message
    expect("a message printed as a stat rises", message("You feel more limber!"),
           Color::StatGain);

    resetPlayer();
    py.misc.current_hp = 60;
    expect("a message printed as you are wounded", message("The kobold hits you."),
           Color::Danger);

    resetPlayer();
    py.misc.exp = 25;  // something died
    expect("a message printed as experience is gained",
           message("The kobold dies in a fit of agony."), Color::Kill);

    resetPlayer();
    expect("a hit that did not kill", message("You hit the kobold."),
           Color::Success);
    resetPlayer();
    expect("a miss", message("You miss the kobold."), Color::Warning);
    resetPlayer();
    expect("ordinary information", message("You have 3 Rations of Food (e)."),
           Color::Normal);

    // --- Update.doc: the "-more-" prompt is deliberately not colour coded,
    // "thus not to spoil the surprise of a monster-kill".
    resetPlayer();
    py.misc.exp = 99;
    expect("the -more- prompt while a kill is pending", message(" -more-"),
           Color::Normal);

    resetPlayer();
    expect("a yes/no prompt", message("Do you want to quit? [y/n]"), Color::Normal);
    resetPlayer();
    expect("an input prompt", message("Enter your player's name:"), Color::Normal);

    // --- The dungeon viewport is never text, so it is never coloured here.
    expect("anything drawn in the map area",
           moria::engine::colours::forText(10, kMapColumn, "#####"), Color::Normal);

    // --- The palette these map onto is Henrik's, not an approximation.
    expectTrue("Normal is the bone white of ColourTable[1]",
               moria::gfx::palette_index(Color::Normal) == 1);
    expectTrue("Danger is red", moria::gfx::palette_index(Color::Danger) == 15);
    expectTrue("Warning is yellow", moria::gfx::palette_index(Color::Warning) == 5);
    expectTrue("Success is light green", moria::gfx::palette_index(Color::Success) == 6);
    expectTrue("Kill is light blue", moria::gfx::palette_index(Color::Kill) == 10);
    expectTrue("StatLoss is dark red", moria::gfx::palette_index(Color::StatLoss) == 13);
    expectTrue("StatGain is blue", moria::gfx::palette_index(Color::StatGain) == 12);

    // --- And finally that the decision reaches the glass. Everything above
    // tests the policy; this drives a string through the same shim the game
    // writes through, renders it, and looks at the pixels. A correct policy
    // wired to nothing would pass every assertion above.
    resetPlayer();
    setHitPoints(20, 100);  // 20% -- red, by the rule checked earlier

    moria::ui::Options options;
    options.headless = true;
    moria::engine::setFrontendOptions(options);

    if (initscr() == nullptr) {
        std::printf("FAIL could not open the display to check the rendering\n");
        ++g_failures;
    } else {
        mvaddstr(kCurrentHpRow, 0, "CHP      20");
        refresh();

        const char *shot = "colour-test.bmp";
        if (!moria::engine::saveScreenshot(shot)) {
            std::printf("FAIL could not write %s\n", shot);
            ++g_failures;
        } else {
            const moria::gfx::Rgb red = moria::gfx::rgb(Color::Danger);
            const int painted = countPixels(shot, kCurrentHpRow, red);
            expectTrue("the hit point line is actually drawn in red pixels",
                       painted > 0);
            std::printf("     %d red pixels on row %d\n", painted, kCurrentHpRow);

            const moria::gfx::Rgb white = moria::gfx::rgb(Color::Normal);
            expectTrue("and not in the normal white",
                       countPixels(shot, kCurrentHpRow, white) == 0);
        }
        endwin();
    }

    if (g_failures != 0) {
        std::printf("\n%d failure(s)\n", g_failures);
        return 1;
    }
    std::printf("\nall colour rules hold\n");
    return 0;
}
