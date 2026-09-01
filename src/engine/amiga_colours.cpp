#include "amiga_colours.hpp"

#include <cstring>

#include "headers.h"

namespace moria::engine::colours {
namespace {

// Umoria's own layout, from src/ui.cpp. The stat block is the left thirteen
// columns; the dungeon starts at column 13.
constexpr int kMessageRow = 0;
constexpr int kStatBlockWidth = 13;
constexpr int kFirstStatRow = 6;   // STR, then INT, WIS, DEX, CON, CHR
constexpr int kStatCount = 6;
constexpr int kManaRow = 15;
constexpr int kCurrentHpRow = 17;
constexpr int kStatusRow = 23;

bool contains(const char *haystack, const char *needle) {
    return std::strstr(haystack, needle) != nullptr;
}

// "0-25% red, 25%-75% yellow, 75%-100% light green, 100% white" -- Amiga.doc.
//
// Compared as ratios rather than as an integer percentage: (current * 100) /
// maximum floors, so 251/1000 would come out as 25 and be drawn red despite
// being above the boundary.
ui::Color forVital(int current, int maximum) {
    if (maximum <= 0) {
        return ui::Color::Normal;
    }
    if (current >= maximum) {
        return ui::Color::Normal;      // white
    }
    const int64_t value = current;
    const int64_t limit = maximum;
    if (value * 4 <= limit) {
        return ui::Color::Danger;      // red, up to and including 25%
    }
    if (value * 4 <= limit * 3) {
        return ui::Color::Warning;     // yellow, up to and including 75%
    }
    return ui::Color::Success;         // light green
}

ui::Color forStatBlock(int row, const char *text) {
    // The six characteristics: yellow while drained, as the documentation
    // says. Read from the game rather than parsed off the screen, so a
    // temporary drain shows even when the printed number has not changed.
    if (row >= kFirstStatRow && row < kFirstStatRow + kStatCount) {
        const int index = row - kFirstStatRow;
        if (py.stats.current[index] < py.stats.max[index]) {
            return ui::Color::Warning;
        }
        return ui::Color::Normal;
    }

    if (row == kManaRow) {
        return forVital(py.misc.current_mana, py.misc.mana);
    }
    if (row == kCurrentHpRow) {
        return forVital(py.misc.current_hp, py.misc.max_hp);
    }

    if (row == kStatusRow) {
        // Update.doc: hungry is yellow, weak is red, "so you'll notice that
        // you are hungry even in a ferocious battle".
        if (contains(text, "Weak")) {
            return ui::Color::Danger;
        }
        if (contains(text, "Hungry")) {
            return ui::Color::Warning;
        }
        // The remaining afflictions are not named in the documentation.
        // Treating them as warnings is an inference, not a quotation.
        for (const char *affliction : {"Blind", "Confused", "Afraid",
                                       "Poisoned", "Paralysed", "Slow"}) {
            if (contains(text, affliction)) {
                return ui::Color::Warning;
            }
        }
    }

    return ui::Color::Normal;
}

bool isPrompt(const char *text) {
    const size_t length = std::strlen(text);
    if (length == 0) {
        return true;
    }
    // Prompts and the -more- marker are never colour coded. Update.doc is
    // explicit that "-more-" must not be, so it cannot give away a kill
    // before the message that follows it.
    if (contains(text, "-more-") || contains(text, "[y/n]") ||
        contains(text, "[press")) {
        return true;
    }
    return text[length - 1] == ':';
}

struct Rule {
    const char *phrase;
    ui::Color colour;
};

// Umoria prints the message *before* it applies the consequence:
// monsterPrintAttackDescription() runs before executeAttackOnPlayer(),
// "You feel weaker." before playerStatRandomDecrease(), "You have picked the
// lock." before py.misc.exp++. So the game's state cannot say what a message
// is about -- at the moment it is written, nothing has happened yet.
//
// The colour therefore comes from the message itself, which is also what
// Henrik was choosing between when he coloured each call site by hand. The
// phrases below are taken from Umoria's own source, not invented.
//
// First match wins, so the order matters: "You hit a teleport trap!" must be
// read as a trap before it is read as a hit.
constexpr Rule kRules[] = {
    // Trouble averted. These read like a stat loss but nothing changed, and
    // they have to be caught before the loss phrases they contain.
    {"but it passes", ui::Color::Warning},
    {"it passes", ui::Color::Warning},
    {"is sustained", ui::Color::Warning},
    {"resists the", ui::Color::Warning},
    {"quickly clears", ui::Color::Warning},

    // Dark red: a characteristic has been reduced.
    {"You feel weaker", ui::Color::StatLoss},
    {"You feel weakened", ui::Color::StatLoss},
    {"You feel more clumsy", ui::Color::StatLoss},
    {"You feel very naive", ui::Color::StatLoss},
    {"You feel very sick", ui::Color::StatLoss},
    {"You feel very sore", ui::Color::StatLoss},
    {"Your health is damaged", ui::Color::StatLoss},
    {"You have damaged your health", ui::Color::StatLoss},
    {"Your wisdom is drained", ui::Color::StatLoss},
    {"trouble thinking clearly", ui::Color::StatLoss},
    {"memories fade", ui::Color::StatLoss},

    // Blue: a characteristic has been raised or restored.
    {"bulging muscles", ui::Color::StatGain},
    {"You feel more dexterous", ui::Color::StatGain},
    {"You feel more limber", ui::Color::StatGain},
    {"You feel more experienced", ui::Color::StatGain},
    {"You feel less clumsy", ui::Color::StatGain},
    {"You feel warm all over", ui::Color::StatGain},
    {"returning", ui::Color::StatGain},

    // Light blue: you killed a monster. The chest is not a monster.
    {"You have destroyed the chest", ui::Color::Warning},
    {"You have slain", ui::Color::Kill},
    {"You have destroyed", ui::Color::Kill},
    {"dies in a fit of agony", ui::Color::Kill},
    {"dies", ui::Color::Kill},

    // Red: you are hurt, or something else really bad happens. These are the
    // verbs from monsterPrintAttackDescription().
    {"trap!", ui::Color::Danger},
    {"hits you", ui::Color::Danger},
    {"bites you", ui::Color::Danger},
    {"claws you", ui::Color::Danger},
    {"stings you", ui::Color::Danger},
    {"touches you", ui::Color::Danger},
    {"kicks you", ui::Color::Danger},
    {"gazes at you", ui::Color::Danger},
    {"breathes on you", ui::Color::Danger},
    {"spits on you", ui::Color::Danger},
    {"embraces you", ui::Color::Danger},
    {"crawls on you", ui::Color::Danger},
    {"horrible wail", ui::Color::Danger},
    {"cloud of spores", ui::Color::Danger},
    {"You die", ui::Color::Danger},
    {"You are enveloped", ui::Color::Danger},

    // Green: you hit a monster, or succeeded at something.
    {"You hit", ui::Color::Good},
    {"good hit", ui::Color::Good},
    {"excellent hit", ui::Color::Good},
    {"superb hit", ui::Color::Good},
    {"GREAT* hit", ui::Color::Good},
    {"You have picked the lock", ui::Color::Good},
    {"You have learned", ui::Color::Good},
    {"You feel better", ui::Color::Good},

    // Yellow: trouble, or you failed to do something.
    {"You miss", ui::Color::Warning},
    {"You failed", ui::Color::Warning},
    {"You have no", ui::Color::Warning},
    {"You cannot", ui::Color::Warning},
    {"You are too", ui::Color::Warning},
    {"There is nothing", ui::Color::Warning},
    {"Nothing happens", ui::Color::Warning},
    {"You feel confused", ui::Color::Warning},
    {"You are confused", ui::Color::Warning},
    {"You feel terrified", ui::Color::Warning},
    {"You are afraid", ui::Color::Warning},
    {"You are blind", ui::Color::Warning},
    {"You are poisoned", ui::Color::Warning},
    {"You are paralysed", ui::Color::Warning},
    {"have no room", ui::Color::Warning},
    {"is in your way", ui::Color::Warning},
    {"You see nothing", ui::Color::Warning},
};

ui::Color forMessage(const char *text) {
    if (isPrompt(text)) {
        return ui::Color::Normal;
    }
    for (const Rule &rule : kRules) {
        if (contains(text, rule.phrase)) {
            return rule.colour;
        }
    }
    return ui::Color::Normal;
}

}  // namespace

ui::Color forText(int row, int col, const char *text) {
    if (text == nullptr) {
        return ui::Color::Normal;
    }
    if (row == kMessageRow) {
        return forMessage(text);
    }
    if (col < kStatBlockWidth) {
        return forStatBlock(row, text);
    }
    return ui::Color::Normal;
}

}  // namespace moria::engine::colours
