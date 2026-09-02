#include "amiga_web.hpp"

#ifdef __EMSCRIPTEN__

#include <emscripten.h>

#include <cstdio>

namespace moria::engine {
const char *webMountSaves() {
    // The mount and the initial load happen in src/engine/web_pre.js, before
    // main() runs, held open by a run dependency. Nothing to wait for here.
    return "/saves/game.sav";
}

void webFlushSaves() {
    EM_ASM({
        if (Module.moriaFlushSaves) {
            Module.moriaFlushSaves();
        }
    });
}

void webExitToBrowser() {
    webFlushSaves();

    // Umoria ends by calling exit(0). A browser build must not: that tears
    // the runtime down before the IndexedDB write can land, and there is
    // nothing to return to anyway. This leaves main() without stopping the
    // runtime, so the pending write completes, the last screen stays on the
    // canvas, and the tab stays responsive. Closing a game in a browser means
    // closing the tab.
    std::printf("moria: saved. You can close this tab.\n");
    std::fflush(stdout);
    emscripten_exit_with_live_runtime();
}

}  // namespace moria::engine

#else

namespace moria::engine {

const char *webMountSaves() {
    return nullptr;  // a native build just uses the filesystem
}

void webFlushSaves() {}

}  // namespace moria::engine

#endif
