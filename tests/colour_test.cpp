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

// Counts pixels on one text row of the saved screen: those matching `wanted`,
// and every pixel that is not the black background. A row is correctly
// coloured only when those two counts are equal -- otherwise some of the text
// is one colour and the rest another.
//
// save_screenshot() writes an uncompressed 24-bit bottom-up BMP.
struct RowPixels {
    int matching = 0;
    int foreground = 0;
};

RowPixels countRow(const char *path, int text_row, moria::gfx::Rgb wanted) {
    RowPixels counted;

    FILE *file = fopen(path, "rb");
    if (file == nullptr) {
        return counted;
    }

    unsigned char header[54];
    if (fread(header, 1, sizeof(header), file) != sizeof(header)) {
        fclose(file);
        return counted;
    }
    const int width = *reinterpret_cast<int *>(header + 18);
    const int height = *reinterpret_cast<int *>(header + 22);
    const int offset = *reinterpret_cast<int *>(header + 10);
    const int stride = ((width * 3) + 3) & ~3;

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
            if (bgr[0] != 0 || bgr[1] != 0 || bgr[2] != 0) {
                ++counted.foreground;
            }
            if (bgr[2] == wanted.r && bgr[1] == wanted.g && bgr[0] == wanted.b) {
                ++counted.matching;
            }
        }
    }

    fclose(file);
    return counted;
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

    // The boundaries, where an integer percentage would floor and widen the
    // red and yellow bands by almost a whole point.
    setHitPoints(250, 1000);
    expect("hit points at exactly 25.0%",
           moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"), Color::Danger);
    setHitPoints(251, 1000);
    expect("hit points at 25.1%",
           moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"), Color::Warning);
    setHitPoints(750, 1000);
    expect("hit points at exactly 75.0%",
           moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"), Color::Warning);
    setHitPoints(751, 1000);
    expect("hit points at 75.1%",
           moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"), Color::Success);
    setHitPoints(1000, 1000);
    expect("hit points at 1000/1000",
           moria::engine::colours::forText(kCurrentHpRow, 0, "CHP"), Color::Normal);
    setHitPoints(100, 100);

    py.misc.current_mana = 10;
    py.misc.mana = 100;
    expect("mana at 10%", moria::engine::colours::forText(kManaRow, 0, "MANA"),
           Color::Danger);
    py.misc.current_mana = 250;
    py.misc.mana = 1000;
    expect("mana at exactly 25.0%",
           moria::engine::colours::forText(kManaRow, 0, "MANA"), Color::Danger);
    py.misc.current_mana = 251;
    expect("mana at 25.1%",
           moria::engine::colours::forText(kManaRow, 0, "MANA"), Color::Warning);
    py.misc.current_mana = 750;
    expect("mana at exactly 75.0%",
           moria::engine::colours::forText(kManaRow, 0, "MANA"), Color::Warning);
    py.misc.current_mana = 751;
    expect("mana at 75.1%",
           moria::engine::colours::forText(kManaRow, 0, "MANA"), Color::Success);
    py.misc.current_mana = 1000;
    expect("mana at 1000/1000",
           moria::engine::colours::forText(kManaRow, 0, "MANA"), Color::Normal);
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

    // --- Amiga.doc's message colours.
    //
    // These run in the order the engine actually uses: Umoria prints the
    // message first and applies the consequence afterwards. Each case checks
    // both halves -- that the message which caused something is coloured, and
    // that the next ordinary message is not coloured by the change that has
    // since landed.
    resetPlayer();
    expect("a monster's attack, printed before the damage lands",
           message("The kobold hits you."), Color::Danger);
    py.misc.current_hp = 60;  // executeAttackOnPlayer() runs now
    expect("the next ordinary message, after the damage landed",
           message("You have 3 Rations of Food (e)."), Color::Normal);

    resetPlayer();
    expect("a stat drain, printed before the stat drops",
           message("You feel weaker."), Color::StatLoss);
    py.stats.current[0] = 16;  // playerStatRandomDecrease() runs now
    expect("the next ordinary message, after the stat dropped",
           message("You have 3 Rations of Food (e)."), Color::Normal);

    resetPlayer();
    expect("picking a lock, printed before the experience is awarded",
           message("You have picked the lock."), Color::Good);
    py.misc.exp++;  // py.misc.exp++ runs now
    expect("the next ordinary message, after the experience was awarded",
           message("You have 3 Rations of Food (e)."), Color::Normal);

    // A drain that was resisted must not read as a drain, even though its
    // text contains one.
    expect("a sustained drain",
           message("You feel weaker for a moment, but it passes."),
           Color::Warning);
    expect("a resisted disease",
           message("Your body resists the effects of the disease."),
           Color::Warning);

    expect("a stat gain", message("Wow!  What bulging muscles!"),
           Color::StatGain);
    expect("a restored characteristic",
           message("You feel your strength returning."), Color::StatGain);

    expect("a kill", message("You have slain the kobold."), Color::Kill);
    expect("a monster dying", message("The kobold dies in a fit of agony."),
           Color::Kill);
    expect("destroying a chest, which is not a monster",
           message("You have destroyed the chest."), Color::Warning);

    // Amiga.doc: green for a hit, which is not the light green of healthy
    // vitals. Both exist in the palette and they are different colours.
    expect("a hit that did not kill", message("You hit the kobold."),
           Color::Good);
    expect("a great hit", message("It was a *GREAT* hit! (x5 damage)"),
           Color::Good);
    expect("a trap, which is not a hit", message("You hit a teleport trap!"),
           Color::Danger);
    expect("a miss", message("You miss the kobold."), Color::Warning);
    expect("ordinary information", message("You have 3 Rations of Food (e)."),
           Color::Normal);

    // --- Update.doc: the "-more-" prompt is deliberately not colour coded,
    // "thus not to spoil the surprise of a monster-kill".
    expect("the -more- prompt", message(" -more-"), Color::Normal);

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
    expectTrue("Success is the light green of healthy vitals",
               moria::gfx::palette_index(Color::Success) == 6);
    expectTrue("Good is the green of a successful hit, a different colour",
               moria::gfx::palette_index(Color::Good) == 7);
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
        mvaddstr(kMessageRow, 0, "You hit the kobold.");
        refresh();

        const char *shot = "colour-test.bmp";
        if (!moria::engine::saveScreenshot(shot)) {
            std::printf("FAIL could not write %s\n", shot);
            ++g_failures;
        } else {
            // Every drawn pixel on the row must be the right colour, not just
            // one of them: a first-glyph-red, rest-yellow rendering would
            // otherwise pass.
            const RowPixels hp = countRow(shot, kCurrentHpRow,
                                          moria::gfx::rgb(Color::Danger));
            expectTrue("the hit point line is drawn, at 20% health",
                       hp.foreground > 0);
            expectTrue("and every pixel of it is red",
                       hp.matching == hp.foreground);
            std::printf("     row %d: %d of %d drawn pixels are red\n",
                        kCurrentHpRow, hp.matching, hp.foreground);

            const RowPixels hit = countRow(shot, kMessageRow,
                                           moria::gfx::rgb(Color::Good));
            expectTrue("the hit message is drawn", hit.foreground > 0);
            expectTrue("and every pixel of it is green, not light green",
                       hit.matching == hit.foreground);
            std::printf("     row %d: %d of %d drawn pixels are green\n",
                        kMessageRow, hit.matching, hit.foreground);

            const RowPixels light = countRow(shot, kMessageRow,
                                             moria::gfx::rgb(Color::Success));
            expectTrue("the hit message uses none of the vitals' light green",
                       light.matching == 0);
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
