// Browser persistence.
//
// Emscripten's filesystem lives in memory and is gone when the tab closes, so
// the save directory is mounted as IDBFS and synchronised with IndexedDB:
// read in once at startup, written back when the game shuts down.
//
// Both calls block until the browser has finished, which is only possible
// because the browser build is compiled with Asyncify -- the same mechanism
// that lets Umoria keep reading keys from deep inside its call stack.
//
// On native builds both are no-ops and the save file is an ordinary file.
#pragma once

namespace moria::engine {

// Mounts the save directory and loads it from IndexedDB. Returns the path
// saves should be written to, or nullptr to leave the default alone.
const char *webMountSaves();

// Writes the save directory back to IndexedDB.
void webFlushSaves();

// The browser's replacement for exit(). Flushes saves, waits for the write to
// land, and then parks: the last screen stays up and the tab stays
// responsive. Never returns. On native builds this is a no-op and the caller
// goes on to exit() as usual.
void webExitToBrowser();

}  // namespace moria::engine
