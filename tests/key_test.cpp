// Assertions on the keyboard mapping.
//
// SDL_KeyboardEvent::key is the *unmodified* keycode: Shift+8 arrives as '8'.
// Moria cares which character was actually typed -- '*' lists the inventory,
// '>' and '<' take the stairs, '?' opens help, '+' is Henrik's look command --
// so the frontend asks SDL to apply the modifiers. Without that, several
// commands are simply unreachable, and taking the stairs is impossible.
#include <SDL3/SDL.h>

#include <cstdio>

#include "ui.hpp"

namespace {

int g_failures = 0;

void expect(const char *what, int scancode, unsigned int mod, int want) {
    const int got = moria::ui::translate_key_press(scancode, mod);
    char shown[8];
    if (want > 31 && want < 127) {
        std::snprintf(shown, sizeof(shown), "'%c'", (char) want);
    } else {
        std::snprintf(shown, sizeof(shown), "%d", want);
    }
    if (got == want) {
        std::printf("ok   %-34s %s\n", what, shown);
        return;
    }
    std::printf("FAIL %-34s expected %s, got %d\n", what, shown, got);
    ++g_failures;
}

}  // namespace

int main() {
    SDL_SetHint(SDL_HINT_VIDEO_DRIVER, "dummy");
    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::printf("FAIL could not initialise SDL: %s\n", SDL_GetError());
        return 1;
    }

    const unsigned int none = SDL_KMOD_NONE;
    const unsigned int shift = SDL_KMOD_LSHIFT;

    // Unshifted keys are unaffected.
    expect("plain 8", SDL_SCANCODE_8, none, '8');
    expect("plain a", SDL_SCANCODE_A, none, 'a');
    expect("plain period", SDL_SCANCODE_PERIOD, none, '.');

    // The characters that were unreachable before.
    expect("shift+8 lists the inventory", SDL_SCANCODE_8, shift, '*');
    expect("shift+period descends stairs", SDL_SCANCODE_PERIOD, shift, '>');
    expect("shift+comma ascends stairs", SDL_SCANCODE_COMMA, shift, '<');
    expect("shift+slash opens help", SDL_SCANCODE_SLASH, shift, '?');
    expect("shift+1 is an exclamation", SDL_SCANCODE_1, shift, '!');
    expect("shift+equals is Henrik's look", SDL_SCANCODE_EQUALS, shift, '+');
    expect("shift+semicolon is a colon", SDL_SCANCODE_SEMICOLON, shift, ':');
    expect("shift+minus is an underscore", SDL_SCANCODE_MINUS, shift, '_');
    expect("shift+a is a capital", SDL_SCANCODE_A, shift, 'A');

    // Movement still arrives as Moria's direction digits.
    expect("keypad 8 moves north", SDL_SCANCODE_KP_8, none, '8');
    expect("the up arrow moves north", SDL_SCANCODE_UP, none, '8');
    expect("keypad 2 moves south", SDL_SCANCODE_KP_2, none, '2');
    expect("shift+keypad 4 runs west", SDL_SCANCODE_KP_4, shift, '4');

    expect("escape", SDL_SCANCODE_ESCAPE, none, moria::ui::kKeyEscape);
    expect("return", SDL_SCANCODE_RETURN, none, moria::ui::kKeyEnter);

    SDL_Quit();

    if (g_failures != 0) {
        std::printf("\n%d failure(s)\n", g_failures);
        return 1;
    }
    std::printf("\nevery command character is reachable\n");
    return 0;
}
