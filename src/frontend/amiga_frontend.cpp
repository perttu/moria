// SDL3 implementation of the display API.
//
// Everything is composed into a 640x200 render target at 1:1, exactly as the
// Amiga screen was, and only then scaled into whatever window or canvas the
// host happens to give us. Scaling is nearest-neighbour and preserves the
// 3.2:1 aspect ratio; unused area is letterboxed, never stretched.
#include "ui.hpp"

#include <SDL3/SDL.h>

#include <algorithm>
#include <cstring>

#include "amiga_palette.hpp"
#include "amiga_tiles.hpp"
#include "font8x8.generated.hpp"
#include "moria_gfx.generated.hpp"
#include "moria_gfxsmall.generated.hpp"
#include "moria_title.generated.hpp"

namespace moria::ui {
namespace {

struct State {
    SDL_Window *window = nullptr;
    SDL_Renderer *renderer = nullptr;
    SDL_Texture *framebuffer = nullptr;
    SDL_Texture *gfx = nullptr;
    SDL_Texture *gfx_small = nullptr;
    SDL_Texture *title = nullptr;
    SDL_Texture *font = nullptr;
    bool fullscreen = false;
    bool quit_requested = false;
    int scale = 2;
};

State g;

SDL_Texture *texture_from_image(SDL_Renderer *renderer, const assets::Image &image) {
    SDL_Texture *tex = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32,
                                         SDL_TEXTUREACCESS_STATIC,
                                         image.width, image.height);
    if (tex == nullptr) {
        SDL_Log("could not create texture: %s", SDL_GetError());
        return nullptr;
    }
    SDL_UpdateTexture(tex, nullptr, image.rgba, image.width * 4);
    SDL_SetTextureScaleMode(tex, SDL_SCALEMODE_NEAREST);
    return tex;
}

// One 128x128 atlas holding all 256 glyphs, 16 to a row, white with the glyph
// shape in the alpha channel. Colour comes from SDL_SetTextureColorMod, which
// keeps a coloured string to one draw call per character.
SDL_Texture *build_font_texture(SDL_Renderer *renderer) {
    constexpr int kAtlas = 128;
    static unsigned char pixels[kAtlas * kAtlas * 4];
    std::memset(pixels, 0, sizeof(pixels));

    for (int code = 0; code < 256; ++code) {
        const int cell_x = (code % 16) * 8;
        const int cell_y = (code / 16) * 8;
        for (int row = 0; row < 8; ++row) {
            const std::uint8_t bits = kFont8x8[code][row];
            for (int col = 0; col < 8; ++col) {
                if ((bits & (0x80 >> col)) == 0) {
                    continue;
                }
                const int offset = ((cell_y + row) * kAtlas + cell_x + col) * 4;
                pixels[offset + 0] = 0xFF;
                pixels[offset + 1] = 0xFF;
                pixels[offset + 2] = 0xFF;
                pixels[offset + 3] = 0xFF;
            }
        }
    }

    SDL_Texture *tex = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32,
                                         SDL_TEXTUREACCESS_STATIC, kAtlas, kAtlas);
    if (tex == nullptr) {
        SDL_Log("could not create font texture: %s", SDL_GetError());
        return nullptr;
    }
    SDL_UpdateTexture(tex, nullptr, pixels, kAtlas * 4);
    SDL_SetTextureScaleMode(tex, SDL_SCALEMODE_NEAREST);
    SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_BLEND);
    return tex;
}

// Largest integer-free rect of 640x200 proportions that fits the window,
// centred. Integer multiples are preferred so pixels stay square whenever the
// window is big enough for one.
SDL_FRect letterbox(int window_w, int window_h) {
    const float scale = std::min(static_cast<float>(window_w) / kScreenWidth,
                                static_cast<float>(window_h) / kScreenHeight);
    const float integer_scale = (scale >= 1.0f) ? SDL_floorf(scale) : scale;
    const float w = kScreenWidth * integer_scale;
    const float h = kScreenHeight * integer_scale;
    return SDL_FRect{(window_w - w) * 0.5f, (window_h - h) * 0.5f, w, h};
}

void fill_cell(int col, int row, gfx::Rgb colour) {
    const SDL_FRect dst{static_cast<float>(col * kCellSize),
                        static_cast<float>(row * kCellSize),
                        static_cast<float>(kCellSize),
                        static_cast<float>(kCellSize)};
    SDL_SetRenderDrawColor(g.renderer, colour.r, colour.g, colour.b, 0xFF);
    SDL_RenderFillRect(g.renderer, &dst);
}

int translate_key(const SDL_KeyboardEvent &key) {
    switch (key.key) {
        case SDLK_ESCAPE: return kKeyEscape;
        case SDLK_RETURN:
        case SDLK_KP_ENTER: return kKeyEnter;
        case SDLK_BACKSPACE: return kKeyBackspace;

        // Arrows and the numeric keypad both produce Moria's original
        // direction digits, so Shift+numpad running and Ctrl+numpad
        // tunnelling arrive as a digit plus a modifier flag.
        case SDLK_KP_1: case SDLK_END: return '1';
        case SDLK_KP_2: case SDLK_DOWN: return '2';
        case SDLK_KP_3: case SDLK_PAGEDOWN: return '3';
        case SDLK_KP_4: case SDLK_LEFT: return '4';
        case SDLK_KP_5: return '5';
        case SDLK_KP_6: case SDLK_RIGHT: return '6';
        case SDLK_KP_7: case SDLK_HOME: return '7';
        case SDLK_KP_8: case SDLK_UP: return '8';
        case SDLK_KP_9: case SDLK_PAGEUP: return '9';
        default: break;
    }

    // SDL keycodes for printable keys are their Unicode values.
    const SDL_Keycode code = key.key;
    if (code >= 32 && code < 127) {
        if ((key.mod & SDL_KMOD_SHIFT) != 0 && code >= 'a' && code <= 'z') {
            return code - 'a' + 'A';
        }
        return static_cast<int>(code);
    }
    return kKeyNone;
}

KeyEvent from_event(const SDL_KeyboardEvent &key) {
    KeyEvent out;
    out.key = translate_key(key);
    out.shift = (key.mod & SDL_KMOD_SHIFT) != 0;
    out.ctrl = (key.mod & SDL_KMOD_CTRL) != 0;
    out.alt = (key.mod & SDL_KMOD_ALT) != 0;
    out.gui = (key.mod & SDL_KMOD_GUI) != 0;

    // Cmd+Enter on macOS, Ctrl+Enter elsewhere: same gesture, handled here so
    // no caller has to know which platform it is on.
    if (out.key == kKeyEnter && (out.gui || out.ctrl || out.alt)) {
        toggle_fullscreen();
        out.key = kKeyNone;
    }
    return out;
}

}  // namespace

bool init(const Options &options) {
    g.scale = std::max(1, options.scale);
    g.fullscreen = options.fullscreen;

    if (options.headless) {
        // Set through a hint rather than an environment variable, so the
        // caller never has to prefix the command line to run without a
        // display.
        SDL_SetHint(SDL_HINT_VIDEO_DRIVER, "dummy");
    }

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        SDL_Log("SDL_Init failed: %s", SDL_GetError());
        return false;
    }

    SDL_WindowFlags flags = 0;
    if (options.fullscreen) {
        flags |= SDL_WINDOW_FULLSCREEN;
    }
    g.window = SDL_CreateWindow(options.title, kScreenWidth * g.scale,
                                kScreenHeight * g.scale, flags);
    if (g.window == nullptr) {
        SDL_Log("SDL_CreateWindow failed: %s", SDL_GetError());
        return false;
    }

    g.renderer = SDL_CreateRenderer(g.window, options.headless ? SDL_SOFTWARE_RENDERER
                                                               : nullptr);
    if (g.renderer == nullptr) {
        SDL_Log("SDL_CreateRenderer failed: %s", SDL_GetError());
        return false;
    }

    g.framebuffer = SDL_CreateTexture(g.renderer, SDL_PIXELFORMAT_RGBA32,
                                      SDL_TEXTUREACCESS_TARGET,
                                      kScreenWidth, kScreenHeight);
    if (g.framebuffer == nullptr) {
        SDL_Log("could not create the 640x200 framebuffer: %s", SDL_GetError());
        return false;
    }
    SDL_SetTextureScaleMode(g.framebuffer, SDL_SCALEMODE_NEAREST);

    g.gfx = texture_from_image(g.renderer, assets::moria_gfx);
    g.gfx_small = texture_from_image(g.renderer, assets::moria_gfxsmall);
    g.title = texture_from_image(g.renderer, assets::moria_title);
    g.font = build_font_texture(g.renderer);

    return g.gfx != nullptr && g.gfx_small != nullptr && g.title != nullptr
           && g.font != nullptr;
}

void shutdown() {
    for (SDL_Texture *tex : {g.font, g.title, g.gfx_small, g.gfx, g.framebuffer}) {
        if (tex != nullptr) {
            SDL_DestroyTexture(tex);
        }
    }
    g = State{};
    SDL_Quit();
}

void clear() {
    SDL_SetRenderTarget(g.renderer, g.framebuffer);
    SDL_SetRenderDrawColor(g.renderer, 0, 0, 0, 0xFF);
    SDL_RenderClear(g.renderer);
}

void present() {
    SDL_SetRenderTarget(g.renderer, nullptr);
    SDL_SetRenderDrawColor(g.renderer, 0, 0, 0, 0xFF);
    SDL_RenderClear(g.renderer);

    int window_w = 0;
    int window_h = 0;
    SDL_GetWindowSizeInPixels(g.window, &window_w, &window_h);
    const SDL_FRect dst = letterbox(window_w, window_h);
    SDL_RenderTexture(g.renderer, g.framebuffer, nullptr, &dst);
    SDL_RenderPresent(g.renderer);

    SDL_SetRenderTarget(g.renderer, g.framebuffer);
}

void tile(int col, int row, std::uint8_t display_code) {
    const gfx::Tile t = gfx::tile_for(display_code);
    const SDL_FRect src{static_cast<float>(t.x * kCellSize),
                        static_cast<float>(t.y * kCellSize),
                        static_cast<float>(kCellSize),
                        static_cast<float>(kCellSize)};
    const SDL_FRect dst{static_cast<float>(col * kCellSize),
                        static_cast<float>(row * kCellSize),
                        static_cast<float>(kCellSize),
                        static_cast<float>(kCellSize)};
    SDL_SetRenderTarget(g.renderer, g.framebuffer);
    SDL_RenderTexture(g.renderer, g.gfx, &src, &dst);
}

void overview_tile(int map_x, int map_y, std::uint8_t display_code) {
    const gfx::Tile t = gfx::tile_for(display_code);
    const SDL_FRect src{static_cast<float>(t.x * kOverviewCell),
                        static_cast<float>(t.y * kOverviewCell),
                        static_cast<float>(kOverviewCell),
                        static_cast<float>(kOverviewCell)};
    const SDL_FRect dst{static_cast<float>(kOverviewX + map_x * kOverviewCell),
                        static_cast<float>(kOverviewY + map_y * kOverviewCell),
                        static_cast<float>(kOverviewCell),
                        static_cast<float>(kOverviewCell)};
    SDL_SetRenderTarget(g.renderer, g.framebuffer);
    SDL_RenderTexture(g.renderer, g.gfx_small, &src, &dst);
}

void text(int col, int row, const char *str, Color colour) {
    if (str == nullptr) {
        return;
    }
    const gfx::Rgb fg = gfx::rgb(colour);
    SDL_SetRenderTarget(g.renderer, g.framebuffer);
    SDL_SetTextureColorMod(g.font, fg.r, fg.g, fg.b);

    for (int i = 0; str[i] != '\0'; ++i) {
        const int c = col + i;
        if (c >= kCols) {
            break;
        }
        const auto code = static_cast<unsigned char>(str[i]);
        // Text cells are opaque, as they are on a bitplane console.
        fill_cell(c, row, gfx::kPalette[0]);
        const SDL_FRect src{static_cast<float>((code % 16) * 8),
                            static_cast<float>((code / 16) * 8), 8.0f, 8.0f};
        const SDL_FRect dst{static_cast<float>(c * kCellSize),
                            static_cast<float>(row * kCellSize),
                            static_cast<float>(kCellSize),
                            static_cast<float>(kCellSize)};
        SDL_RenderTexture(g.renderer, g.font, &src, &dst);
    }
}

void show_title() {
    SDL_SetRenderTarget(g.renderer, g.framebuffer);
    SDL_RenderTexture(g.renderer, g.title, nullptr, nullptr);
}

void toggle_fullscreen() {
    g.fullscreen = !g.fullscreen;
    SDL_SetWindowFullscreen(g.window, g.fullscreen);
}

KeyEvent poll_key() {
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        if (event.type == SDL_EVENT_QUIT) {
            g.quit_requested = true;
            return KeyEvent{kKeyQuit, false, false, false, false};
        }
        if (event.type == SDL_EVENT_KEY_DOWN) {
            const KeyEvent key = from_event(event.key);
            if (key.key != kKeyNone) {
                return key;
            }
        }
    }
    return KeyEvent{};
}

void delay(unsigned milliseconds) {
    SDL_Delay(milliseconds);
}

// Convenience for native code only. The browser build must never block, so
// nothing on the Emscripten path may call this.
KeyEvent get_key() {
    for (;;) {
        const KeyEvent key = poll_key();
        if (key.key != kKeyNone) {
            return key;
        }
        SDL_Delay(8);
    }
}

bool save_screenshot(const char *path) {
    SDL_SetRenderTarget(g.renderer, g.framebuffer);
    const SDL_Rect whole{0, 0, kScreenWidth, kScreenHeight};
    SDL_Surface *shot = SDL_RenderReadPixels(g.renderer, &whole);
    if (shot == nullptr) {
        SDL_Log("could not read the framebuffer: %s", SDL_GetError());
        return false;
    }

    // Normalise to plain 24-bit RGB before saving. The renderer's native
    // format varies by backend, and a BMP whose layout depends on which
    // driver happened to be in use is no use to a pixel comparison.
    SDL_Surface *rgb = SDL_ConvertSurface(shot, SDL_PIXELFORMAT_RGB24);
    SDL_DestroySurface(shot);
    if (rgb == nullptr) {
        SDL_Log("could not convert the framebuffer to RGB24: %s", SDL_GetError());
        return false;
    }

    const bool ok = SDL_SaveBMP(rgb, path);
    if (!ok) {
        SDL_Log("could not write %s: %s", path, SDL_GetError());
    }
    SDL_DestroySurface(rgb);
    return ok;
}

}  // namespace moria::ui
