// Browser save persistence.
//
// Emscripten's filesystem lives in memory and is gone when the tab closes, so
// the save file is mirrored into the browser's own storage: read back before
// main() runs, written whenever the game saves.
//
// This uses localStorage rather than IndexedDB, which is a deliberate
// deviation from the original plan. IndexedDB is asynchronous, and every way
// of waiting for it here proved unsound: IDBFS's syncfs() never called back
// at all, and holding up startup with a run dependency left the module
// waiting forever when the callback did not arrive. localStorage is
// synchronous, so the restore simply happens, with no callback to miss and no
// interaction with Asyncify. A Moria save is around 5 kB against a budget of
// about 5 MB, so the size limit is not a real constraint.
var MORIA_KEY = 'moria.save';
var MORIA_PATH = '/saves/game.sav';

function moriaNote(text) {
  if (Module.printErr) { Module.printErr('moria: ' + text); }
  else { console.error('moria: ' + text); }
}

Module.preRun = Module.preRun || [];
Module.preRun.push(function () {
  try { FS.mkdir('/saves'); } catch (e) { /* already there */ }

  var stored = null;
  try {
    stored = localStorage.getItem(MORIA_KEY);
  } catch (e) {
    moriaNote('no access to local storage: ' + e);
    return;
  }
  if (!stored) {
    moriaNote('no save stored yet');
    return;
  }

  try {
    var text = atob(stored);
    var bytes = new Uint8Array(text.length);
    for (var i = 0; i < text.length; i++) {
      bytes[i] = text.charCodeAt(i);
    }
    FS.writeFile(MORIA_PATH, bytes);
    moriaNote('restored a save of ' + bytes.length + ' bytes');
  } catch (e) {
    moriaNote('could not restore the save: ' + e);
  }
});

// Called from C++ once the game has written its save file, and again if the
// tab is closing.
Module.moriaFlushSaves = function () {
  var data;
  try {
    data = FS.readFile(MORIA_PATH);
  } catch (e) {
    return;  // nothing saved yet
  }
  try {
    var text = '';
    for (var i = 0; i < data.length; i++) {
      text += String.fromCharCode(data[i]);
    }
    localStorage.setItem(MORIA_KEY, btoa(text));
    moriaNote('stored a save of ' + data.length + ' bytes');
  } catch (e) {
    moriaNote('could not store the save: ' + e);
  }
};

// A player who closes the tab should not lose a save the game already wrote.
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', function () {
    if (Module.moriaFlushSaves) { Module.moriaFlushSaves(); }
  });
}
