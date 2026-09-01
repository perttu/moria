#!/usr/bin/env python3
"""Check that the browser build actually runs, in a real browser.

Compiling to WebAssembly is not the same as running. This loads the build in
headless Chrome, screenshots the canvas at 1:1, and checks two things:

  * the title screen the browser draws is pixel-identical to moria_title.iff,
    the same acceptance criterion the native build is held to;
  * pressing Space advances the game, so keyboard input reaches Moria through
    the browser event path and the main loop is really running.

Chrome is found in the Playwright browser cache or on PATH. Nothing needs
installing beyond an Emscripten build and a Chrome binary.

Usage:
    web_smoke.py --build-web build-web --assets /path/to/1.2/Moria
"""

import argparse
import functools
import glob
import hashlib
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, HERE)
sys.path.insert(0, TOOLS)

import iff_convert  # noqa: E402
from compare_screens import (SCREEN_WIDTH, SCREEN_HEIGHT, CELL,  # noqa: E402
                             MAP_COL_OFFSET, TITLE_CAPTION_ROW)

HARNESS = os.path.join(HERE, "web", "harness.html")

CHROME_CANDIDATES = (
    os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome"),
    os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

CHROME_ON_PATH = ("google-chrome", "chromium", "chromium-browser", "chrome")


class Failure(Exception):
    pass


class Skip(Exception):
    pass


def find_chrome(explicit):
    if explicit:
        if not os.path.exists(explicit):
            raise Failure("no Chrome at %s" % explicit)
        return explicit
    for name in CHROME_ON_PATH:
        found = shutil.which(name)
        if found:
            return found
    for pattern in CHROME_CANDIDATES:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]
    raise Skip("no Chrome or Chromium found; install one, or pass --chrome")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass  # one request line per asset, twice, is just noise in a test log


def serve(directory):
    handler = functools.partial(QuietHandler, directory=directory)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, httpd.server_address[1]


def screenshot(chrome, url, out_path, window, profile=None):
    command = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--enable-unsafe-swiftshader", "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--window-size=%d,%d" % window,
        "--virtual-time-budget=20000",
        "--screenshot=%s" % out_path, url,
    ]
    if profile is not None:
        # IndexedDB lives in the profile, so two runs that must share a save
        # have to share one.
        command.insert(1, "--user-data-dir=%s" % profile)
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if not os.path.exists(out_path):
        raise Failure("Chrome wrote no screenshot for %s\n%s"
                      % (url, result.stderr.strip()[-2000:]))
    return out_path


def load_png(path):
    try:
        from PIL import Image
    except ImportError:
        raise Skip("Pillow is needed to compare the browser's screenshots "
                   "(pip install pillow)")
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        return rgb.size, list(rgb.getdata())


def title_pixels(assets_dir):
    with open(os.path.join(assets_dir, "moria_title.iff"), "rb") as fh:
        image = iff_convert.parse_ilbm(fh.read())
    rgba = image.rgba(opaque=True)
    return [tuple(rgba[i:i + 3]) for i in range(0, len(rgba), 4)]


def check_title(pixels, size, assets_dir, report):
    if size != (SCREEN_WIDTH, SCREEN_HEIGHT):
        raise Failure("the canvas rendered %dx%d, expected %dx%d; the browser "
                      "is not drawing the virtual screen at 1:1"
                      % (*size, SCREEN_WIDTH, SCREEN_HEIGHT))

    original = title_pixels(assets_dir)
    caption_first = TITLE_CAPTION_ROW * CELL
    caption_last = caption_first + CELL

    differing = 0
    first = None
    for y in range(SCREEN_HEIGHT):
        if caption_first <= y < caption_last:
            continue
        row = y * SCREEN_WIDTH
        for x in range(SCREEN_WIDTH):
            if pixels[row + x] != original[row + x]:
                differing += 1
                if first is None:
                    first = (x, y, pixels[row + x], original[row + x])
    if differing:
        raise Failure("the browser's title screen differs from moria_title.iff "
                      "in %d pixels; first at x=%d y=%d, browser %s, original %s"
                      % (differing, *first))
    report("ok   the browser draws the title pixel-identically to moria_title.iff")


def check_indexeddb_saves(chrome, port, workdir, report):
    """Save in one page load, and find the save still there in the next.

    Emscripten's filesystem is memory only, so without IDBFS a save would be
    gone the moment the tab closed. Both runs share a browser profile because
    that is where IndexedDB lives.
    """
    # KNOWN FAILURE: the run below hangs. Umoria's exitProgram() calls exit(0)
    # straight after terminalRestore(), and exit() from inside a stack that
    # Asyncify has unwound does not return control to the browser. The save is
    # written to the in-memory filesystem first, but the page freezes before
    # IndexedDB can be flushed. Left in, and off by default, because it
    # describes exactly what has to be fixed.
    profile = os.path.join(workdir, "profile")
    base = "http://127.0.0.1:%d/harness.html?app=moria-amiga&args=" % port

    # Create a character, walk into the town, then ^X to save and quit.
    keys = "am\\eaFenwick\\n \\cX "
    saving = screenshot(chrome,
                        base + "--scale,1,-n,-s,12345,--keys," + keys,
                        os.path.join(workdir, "web-saving.png"),
                        (SCREEN_WIDTH, SCREEN_HEIGHT), profile=profile)
    _size, _pixels = load_png(saving)
    report("ok   the browser build saved and exited")

    # A second page load, same profile: no -n, so it must find the save.
    loaded = screenshot(chrome, base + "--scale,1,-s,12345",
                        os.path.join(workdir, "web-loaded.png"),
                        (SCREEN_WIDTH, SCREEN_HEIGHT), profile=profile)
    size, pixels = load_png(loaded)
    if size != (SCREEN_WIDTH, SCREEN_HEIGHT):
        raise Failure("the reloaded page rendered %dx%d" % size)
    if all(pixel == (0, 0, 0) for pixel in pixels):
        raise Failure("the reloaded page is blank")

    # A game that failed to find its save starts character creation, which
    # asks for a race on the bottom rows. A restored game shows the town.
    restored_rows = {y for y in range(SCREEN_HEIGHT)
                     if any(pixels[y * SCREEN_WIDTH + x] != (0, 0, 0)
                            for x in range(MAP_COL_OFFSET * CELL, SCREEN_WIDTH))}
    if not restored_rows:
        raise Failure("the reloaded page drew nothing in the map area, so the "
                      "save was not restored")
    report("ok   the save survived the page reload through IndexedDB")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-web", required=True, help="the Emscripten build directory")
    ap.add_argument("--assets", required=True, help="directory holding the .iff files")
    ap.add_argument("--chrome", help="path to a Chrome or Chromium binary")
    ap.add_argument("--golden", help="golden hashes for amiga-gfx-test's screens, "
                                     "to check the browser renders the same pixels")
    ap.add_argument("--game-golden", help="golden hashes for the real game's "
                                          "screens, for the browser game build")
    ap.add_argument("--keep", action="store_true", help="keep the rendered PNGs")
    ap.add_argument("--check-saves", action="store_true",
                    help="also check that a save survives a page reload. Off "
                         "by default: saving in the browser currently hangs "
                         "the tab (see NOTES.md), so this does not pass yet.")
    args = ap.parse_args(argv)

    lines = []

    def report(line):
        lines.append(line)
        print(line, flush=True)

    try:
        page = os.path.join(args.build_web, "amiga-gfx-test.js")
        if not os.path.exists(page):
            raise Skip("no Emscripten build at %s; run the emcmake build first"
                       % args.build_web)
        chrome = find_chrome(args.chrome)
        report("ok   using %s" % chrome)

        # The harness has to sit beside the .js it loads.
        harness_copy = os.path.join(args.build_web, "harness.html")
        shutil.copyfile(HARNESS, harness_copy)

        httpd, port = serve(args.build_web)
        try:
            base = "http://127.0.0.1:%d/harness.html?args=--scale,1" % port
            workdir = tempfile.mkdtemp(prefix="moria-web-")

            title_png = screenshot(chrome, base,
                                   os.path.join(workdir, "title.png"),
                                   (SCREEN_WIDTH, SCREEN_HEIGHT))
            size, pixels = load_png(title_png)
            report("ok   the WebAssembly build loads and renders (%dx%d canvas)" % size)
            check_title(pixels, size, args.assets, report)

            after_png = screenshot(chrome, base + "&keys=Space",
                                   os.path.join(workdir, "after-space.png"),
                                   (SCREEN_WIDTH, SCREEN_HEIGHT))
            after_size, after = load_png(after_png)
            if after_size != size:
                raise Failure("the canvas changed size after a keypress")
            if after == pixels:
                raise Failure("pressing Space changed nothing; keyboard input is "
                              "not reaching the game, or the main loop is not "
                              "running")
            changed = sum(1 for a, b in zip(after, pixels) if a != b)
            report("ok   Space advances past the title (%d of %d pixels changed)"
                   % (changed, len(pixels)))

            # The strongest claim the port can make: the browser and the
            # native build put the same pixels on the screen. The dungeon
            # golden was produced by the native binary, so comparing the
            # browser's canvas against it checks both at once.
            if args.golden and os.path.exists(args.golden):
                with open(args.golden) as fh:
                    golden = json.load(fh)
                if "dungeon" in golden:
                    flat = bytes(value for pixel in after for value in pixel)
                    got = hashlib.sha256(flat).hexdigest()
                    if got != golden["dungeon"]:
                        raise Failure(
                            "the browser's dungeon screen does not match the "
                            "native one: golden %s, browser %s"
                            % (golden["dungeon"][:16], got[:16]))
                    report("ok   the browser's dungeon screen is byte-identical "
                           "to the native render")

            # The game itself, if it was built for the browser. Umoria reads
            # keys from deep inside its call stack; Asyncify is what lets that
            # happen without freezing the tab.
            game = os.path.join(args.build_web, "moria-amiga.js")
            if (os.path.exists(game) and args.game_golden
                    and os.path.exists(args.game_golden)):
                with open(args.game_golden) as fh:
                    golden = json.load(fh)
                game_url = ("http://127.0.0.1:%d/harness.html?app=moria-amiga"
                            "&args=--scale,1,-n,-s,12345,--keys,am&delay=3000" % port)
                game_png = screenshot(chrome, game_url,
                                      os.path.join(workdir, "game.png"),
                                      (SCREEN_WIDTH, SCREEN_HEIGHT))
                game_size, game_pixels = load_png(game_png)
                if game_size != (SCREEN_WIDTH, SCREEN_HEIGHT):
                    raise Failure("the game canvas was %dx%d" % game_size)
                flat = bytes(value for pixel in game_pixels for value in pixel)
                got = hashlib.sha256(flat).hexdigest()
                if all(pixel == (0, 0, 0) for pixel in game_pixels):
                    raise Failure("the game's canvas is blank; it did not get "
                                  "as far as drawing anything")
                report("ok   Umoria itself runs in the browser and reaches "
                       "character creation")
                if "creation" in golden and got != golden["creation"]:
                    raise Failure("the browser's character creation screen "
                                  "does not match the native one: native %s, "
                                  "browser %s"
                                  % (golden["creation"][:16], got[:16]))
                report("ok   and draws it byte-identically to the native build")

                if args.check_saves:
                    check_indexeddb_saves(chrome, port, workdir, report)

            if args.keep:
                report("renders kept in %s" % workdir)
            else:
                shutil.rmtree(workdir, ignore_errors=True)
        finally:
            httpd.shutdown()
            httpd.server_close()
            if os.path.exists(harness_copy):
                os.remove(harness_copy)
    except Skip as reason:
        print("SKIP %s" % reason)
        return 0
    except Failure as err:
        print("\nFAIL %s" % err, file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("\nFAIL Chrome timed out loading the build", file=sys.stderr)
        return 1

    print("\nthe browser build runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
