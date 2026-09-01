#!/usr/bin/env python3
"""Drive the real game to known screens and check the pixels.

`amiga-gfx-test` proves the frontend can draw. This proves Umoria is actually
driving it: the binary is started with a fixed seed and a scripted sequence of
keystrokes, run through character creation and into the town, and the screen
it produces is compared against a reviewed golden hash.

One check is structural rather than a hash, and it is the important one: the
dungeon viewport must be drawn from the 8x8 tile atlas, not from the font. If
`panelPutTile` ever stopped routing to `ui::tile`, the game would still run
and still look like a roguelike -- in ASCII. Comparing cells against the atlas
catches that; a hash would too, but only after somebody regenerated it.

Usage:
    game_screens.py --binary build/moria-amiga --assets DIR --workdir DIR \\
        --golden tests/golden_game_screens.json
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, HERE)
sys.path.insert(0, TOOLS)

import iff_convert  # noqa: E402
from compare_screens import (read_bmp, digest, CELL, MAP_COL_OFFSET,  # noqa: E402
                             MAP_ROW_OFFSET, SCREEN_WIDTH, SCREEN_HEIGHT)

MAP_COLS = 66
MAP_ROWS = 22

# A fixed seed makes character rolls and the town layout reproducible.
SEED = "12345"

# Keystrokes are: race a (Human), sex m, ESC to accept the rolled stats,
# class a (Warrior), the name, Return, then a key to leave the character
# sheet. Each screen stops one step earlier than the next.
CREATION = "am"
STATS = "am\\e"
SHEET = "am\\eaFenwick\\n"
TOWN = "am\\eaFenwick\\n "

OVERVIEW = TOWN + "M"

# Wizard mode, so a dungeon level can be reached without playing down to it:
# a space and a 'y' accept its warning, then ^D jumps to level 5.
DUNGEON = " yam\\eaFenwick\\n \\cD5\\n"

SCREENS = {
    "creation": (CREATION, ()),
    "character-sheet": (SHEET, ()),
    "town": (TOWN, ()),
    "overview": (OVERVIEW, ()),
    "dungeon": (DUNGEON, ("-w",)),
}

# Henrik's reduced map: two pixels per dungeon cell, at this pixel origin.
OVERVIEW_X = 122
OVERVIEW_Y = 34
OVERVIEW_CELL = 2


class Failure(Exception):
    pass


def render(binary, keys, out_path, extra=()):
    command = [binary, "--headless", "-n", "-s", SEED, *extra,
               "--keys", keys, "--screenshot", out_path]
    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=120, cwd=os.path.dirname(binary) or ".")
    if not os.path.exists(out_path):
        raise Failure("no screenshot from keys %r\n--- stdout ---\n%s\n"
                      "--- stderr ---\n%s"
                      % (keys, result.stdout.strip(), result.stderr.strip()))
    width, height, rows = read_bmp(out_path)
    if (width, height) != (SCREEN_WIDTH, SCREEN_HEIGHT):
        raise Failure("the game rendered %dx%d, expected %dx%d"
                      % (width, height, SCREEN_WIDTH, SCREEN_HEIGHT))
    return rows


def atlas_tiles(assets_dir):
    """Every 8x8 cell of moria_gfx.iff, as a set of raw RGB blocks."""
    with open(os.path.join(assets_dir, "moria_gfx.iff"), "rb") as fh:
        image = iff_convert.parse_ilbm(fh.read())
    rgba = image.rgba(opaque=True)
    rows = []
    for y in range(image.height):
        start = y * image.width * 4
        row = rgba[start:start + image.width * 4]
        rows.append(bytes(b for i in range(0, len(row), 4) for b in row[i:i + 3]))

    tiles = set()
    for tile_y in range(image.height // CELL):
        for tile_x in range(image.width // CELL):
            block = b"".join(
                rows[tile_y * CELL + line][tile_x * CELL * 3:(tile_x * CELL + CELL) * 3]
                for line in range(CELL))
            tiles.add(block)
    return tiles


def check_viewport_uses_tiles(rows, assets_dir, report):
    tiles = atlas_tiles(assets_dir)

    matched = 0
    total = 0
    for map_y in range(MAP_ROWS):
        for map_x in range(MAP_COLS):
            x = (MAP_COL_OFFSET + map_x) * CELL
            y = (MAP_ROW_OFFSET + map_y) * CELL
            block = b"".join(rows[y + line][x * 3:(x + CELL) * 3]
                             for line in range(CELL))
            if block == bytes(CELL * CELL * 3):
                continue  # unlit, nothing drawn there
            total += 1
            if block in tiles:
                matched += 1

    if total == 0:
        raise Failure("the dungeon viewport is entirely blank; the game drew "
                      "nothing into it")
    if matched != total:
        raise Failure("%d of %d drawn viewport cells are not tiles from "
                      "moria_gfx.iff -- the map is being drawn with the font"
                      % (total - matched, total))
    report("ok   all %d drawn viewport cells come from the tile atlas" % total)


def small_atlas_cells(assets_dir):
    """Every 2x2 cell of moria_gfxsmall.iff, as raw RGB blocks."""
    with open(os.path.join(assets_dir, "moria_gfxsmall.iff"), "rb") as fh:
        image = iff_convert.parse_ilbm(fh.read())
    rgba = image.rgba(opaque=True)
    rows = []
    for y in range(image.height):
        start = y * image.width * 4
        row = rgba[start:start + image.width * 4]
        rows.append(bytes(b for i in range(0, len(row), 4) for b in row[i:i + 3]))

    cells = set()
    for tile_y in range(image.height // OVERVIEW_CELL):
        for tile_x in range(image.width // OVERVIEW_CELL):
            block = b"".join(
                rows[tile_y * OVERVIEW_CELL + line][
                    tile_x * OVERVIEW_CELL * 3:(tile_x * OVERVIEW_CELL + OVERVIEW_CELL) * 3]
                for line in range(OVERVIEW_CELL))
            cells.add(block)
    return cells


def check_overview_uses_small_atlas(rows, assets_dir, report):
    """The reduced map must come from moria_gfxsmall.iff, not from shrinking.

    Umoria's own reduced map is text; Henrik's is a second atlas at two pixels
    per dungeon cell. If the substitution ever stopped happening, the screen
    would still show a plausible map -- made of letters.
    """
    cells = small_atlas_cells(assets_dir)

    drawn = 0
    matched = 0
    for map_y in range(MAP_ROWS * 3):
        for map_x in range(MAP_COLS * 3):
            x = OVERVIEW_X + map_x * OVERVIEW_CELL
            y = OVERVIEW_Y + map_y * OVERVIEW_CELL
            if x + OVERVIEW_CELL > SCREEN_WIDTH or y + OVERVIEW_CELL > SCREEN_HEIGHT:
                continue
            block = b"".join(rows[y + line][x * 3:(x + OVERVIEW_CELL) * 3]
                             for line in range(OVERVIEW_CELL))
            if block == bytes(OVERVIEW_CELL * OVERVIEW_CELL * 3):
                continue
            drawn += 1
            if block in cells:
                matched += 1

    if drawn == 0:
        raise Failure("the reduced map drew nothing at (%d, %d)"
                      % (OVERVIEW_X, OVERVIEW_Y))
    if matched != drawn:
        raise Failure("%d of %d drawn overview cells are not from "
                      "moria_gfxsmall.iff" % (drawn - matched, drawn))
    report("ok   all %d drawn overview cells come from the small atlas, at "
           "(%d, %d)" % (drawn, OVERVIEW_X, OVERVIEW_Y))


def check_save_and_reload(binary, workdir, town_rows, report):
    """Create a character, save and quit, then load the save back.

    The stat block is compared pixel for pixel against the same character
    before saving. A save that loses the character, or loads a different one,
    changes those columns.
    """
    save_path = os.path.join(os.path.abspath(workdir), "roundtrip.sav")
    if os.path.exists(save_path):
        os.remove(save_path)

    # ^X saves and exits, so this run ends on its own.
    written = subprocess.run(
        # Two keys clear the pending help message, then ^X saves and exits;
        # the trailing key acknowledges its own "-more-". The screenshot path
        # is a safety net: without it a script that runs out would block on a
        # keypress nobody can make.
        [binary, "--headless", "-n", "-s", SEED,
         "--keys", TOWN + " \\cX ",
         "--screenshot", os.path.join(os.path.abspath(workdir), "saving.bmp"),
         save_path],
        capture_output=True, text=True, timeout=120,
        cwd=os.path.dirname(binary) or ".")
    if not os.path.exists(save_path):
        raise Failure("saving wrote no file\n--- stdout ---\n%s\n--- stderr ---\n%s"
                      % (written.stdout.strip(), written.stderr.strip()))
    report("ok   ^X saved the game to %s (%d bytes)"
           % (os.path.basename(save_path), os.path.getsize(save_path)))

    reloaded = os.path.join(os.path.abspath(workdir), "reloaded.bmp")
    result = subprocess.run(
        [binary, "--headless", "-s", SEED, "--keys", "  ",
         "--screenshot", reloaded, save_path],
        capture_output=True, text=True, timeout=120,
        cwd=os.path.dirname(binary) or ".")
    if not os.path.exists(reloaded):
        raise Failure("loading the save produced no screen\n--- stdout ---\n%s\n"
                      "--- stderr ---\n%s" % (result.stdout.strip(),
                                              result.stderr.strip()))
    _w, _h, rows = read_bmp(reloaded)

    # Columns 0..12 are the stat block; the dungeon starts at column 13.
    stat_width = MAP_COL_OFFSET * CELL * 3
    differing = 0
    for y in range(CELL, SCREEN_HEIGHT):
        if rows[y][:stat_width] != town_rows[y][:stat_width]:
            differing += 1
    if differing:
        raise Failure("the reloaded character's stat block differs from the "
                      "saved one on %d scanlines" % differing)
    report("ok   the reloaded character is pixel-identical in the stat block")


def check_goldens(digests, golden_path, update, report):
    if update:
        with open(golden_path, "w") as fh:
            json.dump(digests, fh, indent=2, sort_keys=True)
            fh.write("\n")
        report("updated %s" % golden_path)
        return

    if not os.path.exists(golden_path):
        raise Failure("no goldens at %s; re-run with --update after reviewing "
                      "the rendered screens" % golden_path)
    with open(golden_path) as fh:
        golden = json.load(fh)

    for name in SCREENS:
        if name not in golden:
            raise Failure("no golden recorded for the %s screen" % name)
        if golden[name] != digests[name]:
            raise Failure("the %s screen changed: golden %s, rendered %s"
                          % (name, golden[name][:16], digests[name][:16]))
        report("ok   %s matches its golden" % name)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--binary", required=True, help="path to moria-amiga")
    ap.add_argument("--assets", required=True, help="directory holding the .iff files")
    ap.add_argument("--workdir", required=True, help="where to write renders")
    ap.add_argument("--golden", required=True, help="golden hash file")
    ap.add_argument("--update", action="store_true",
                    help="rewrite the goldens instead of comparing")
    args = ap.parse_args(argv)

    os.makedirs(args.workdir, exist_ok=True)

    def report(line):
        print(line, flush=True)

    try:
        binary = os.path.abspath(args.binary)
        if not os.path.exists(binary):
            raise Failure("no binary at %s" % binary)

        rendered = {}
        digests = {}
        for name, (keys, extra) in SCREENS.items():
            path = os.path.join(os.path.abspath(args.workdir), "%s.bmp" % name)
            rendered[name] = render(binary, keys, path, extra)
            digests[name] = digest(rendered[name])
        report("ok   the game runs through character creation into the town")

        check_viewport_uses_tiles(rendered["town"], args.assets, report)
        check_viewport_uses_tiles(rendered["dungeon"], args.assets, report)
        check_overview_uses_small_atlas(rendered["overview"], args.assets, report)
        check_save_and_reload(binary, args.workdir, rendered["town"], report)

        # Determinism: the same seed and the same keys must produce the same
        # screen, or the goldens are meaningless.
        again = render(binary, SCREENS["town"][0],
                       os.path.join(os.path.abspath(args.workdir), "town-again.bmp"))
        if digest(again) != digests["town"]:
            raise Failure("two runs with the same seed produced different "
                          "screens; the goldens cannot be trusted")
        report("ok   the same seed and keys reproduce the same screen")

        check_goldens(digests, args.golden, args.update, report)
    except Failure as err:
        print("\nFAIL %s" % err, file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("\nFAIL the game did not exit; a scripted key was probably "
              "consumed by a prompt that was not expected", file=sys.stderr)
        return 1

    print("\nUmoria is driving the Amiga frontend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
