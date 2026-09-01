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
ui::Color forVital(int current, int maximum) {
    if (maximum <= 0) {
        return ui::Color::Normal;
    }
    if (current >= maximum) {
        return ui::Color::Normal;      // white
    }
    const int percent = (current * 100) / maximum;
    if (percent <= 25) {
        return ui::Color::Danger;      // red
    }
    if (percent <= 75) {
        return ui::Color::Warning;     // yellow
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

// State as it was when the previous message was printed. Comparing against it
// is how a stat change or a wound is detected, which is more reliable than
// reading the message text: the documentation defines these cases by what
// happened, not by what was said.
struct Snapshot {
    bool valid = false;
    int16_t current_hp = 0;
    int32_t exp = 0;
    uint8_t stats[kStatCount] = {0};
};

Snapshot g_previous;

Snapshot takeSnapshot() {
    Snapshot snapshot;
    snapshot.valid = true;
    snapshot.current_hp = py.misc.current_hp;
    snapshot.exp = static_cast<int32_t>(py.misc.exp);
    for (int i = 0; i < kStatCount; ++i) {
        snapshot.stats[i] = py.stats.current[i];
    }
    return snapshot;
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

ui::Color classifyMessageText(const char *text) {
    // You killed something.
    for (const char *phrase : {"You have slain", "You have destroyed",
                               "You have killed", "dies", "die."}) {
        if (contains(text, phrase)) {
            return ui::Color::Kill;
        }
    }
    // You succeeded.
    for (const char *phrase : {"You hit", "great hit", "You have learned",
                               "You feel better", "You feel much better",
                               "You are no longer", "You feel less"}) {
        if (contains(text, phrase)) {
            return ui::Color::Success;
        }
    }
    // Trouble, or you failed at something.
    for (const char *phrase : {"You miss", "You failed", "You have no",
                               "You cannot", "There is nothing", "You are too",
                               "Nothing happens", "You feel confused",
                               "You are confused", "You are afraid",
                               "You are blind", "You are poisoned",
                               "You are paralysed", "have no room",
                               "is in your way", "You see nothing"}) {
        if (contains(text, phrase)) {
            return ui::Color::Warning;
        }
    }
    return ui::Color::Normal;
}

ui::Color forMessage(const char *text) {
    if (isPrompt(text)) {
        return ui::Color::Normal;
    }

    const Snapshot now = takeSnapshot();
    const Snapshot before = g_previous;
    g_previous = now;

    if (!game.character_generated) {
        // Character creation prints plenty of text through the message line
        // before there is any state worth comparing.
        return classifyMessageText(text);
    }

    if (before.valid) {
        // A stat moved. Dark red down, blue up -- the two cases Amiga.doc
        // singles out as most worth noticing.
        for (int i = 0; i < kStatCount; ++i) {
            if (now.stats[i] < before.stats[i]) {
                return ui::Color::StatLoss;
            }
        }
        for (int i = 0; i < kStatCount; ++i) {
            if (now.stats[i] > before.stats[i]) {
                return ui::Color::StatGain;
            }
        }
        // Experience went up without a stat change: something died.
        if (now.exp > before.exp) {
            return ui::Color::Kill;
        }
        // You are hurt.
        if (now.current_hp < before.current_hp) {
            return ui::Color::Danger;
        }
    }

    return classifyMessageText(text);
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
