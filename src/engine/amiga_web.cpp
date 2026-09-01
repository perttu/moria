#include "amiga_web.hpp"

#ifdef __EMSCRIPTEN__

#include <emscripten.h>

#include <cstdio>

namespace moria::engine {
namespace {

// Set from JavaScript when a syncfs call completes. Asyncify lets us wait for
// it without returning to the browser's event loop by hand.
volatile int g_sync_state = 0;  // 0 pending, 1 done, -1 failed

void waitForSync(const char *what) {
    const int kTimeoutMs = 10000;
    int waited = 0;
    while (g_sync_state == 0 && waited < kTimeoutMs) {
        emscripten_sleep(10);
        waited += 10;
    }
    if (g_sync_state != 1) {
        std::fprintf(stderr, "moria: %s did not complete (%d)\n", what,
                     g_sync_state);
    }
}

}  // namespace

extern "C" EMSCRIPTEN_KEEPALIVE void moriaSyncDone(int ok) {
    g_sync_state = ok ? 1 : -1;
}

const char *webMountSaves() {
    g_sync_state = 0;
    EM_ASM({
        try {
            FS.mkdir('/saves');
        } catch (e) {
            // already there
        }
        FS.mount(IDBFS, {}, '/saves');
        // true: bring what IndexedDB already holds into the in-memory FS.
        FS.syncfs(true, function (err) {
            Module.ccall('moriaSyncDone', null, ['number'], [err ? 0 : 1]);
        });
    });
    waitForSync("loading saves from IndexedDB");
    return "/saves/game.sav";
}

void webFlushSaves() {
    // Deliberately not waited on. This runs from endwin(), which
    // exitProgram() calls immediately before exit(0), and blocking there --
    // inside a stack Asyncify is already unwinding -- wedges the page.
    // IndexedDB writes are fast and the browser finishes them after the
    // module has stopped.
    EM_ASM({
        FS.syncfs(false, function (err) {
            if (err) {
                console.error('moria: could not write saves to IndexedDB', err);
            }
        });
    });
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
