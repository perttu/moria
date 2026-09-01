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

SCREENS = {
    "creation": CREATION,
    "character-sheet": SHEET,
    "town": TOWN,
}


class Failure(Exception):
    pass


def render(binary, keys, out_path):
    command = [binary, "--headless", "-n", "-s", SEED,
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
        for name, keys in SCREENS.items():
            path = os.path.join(os.path.abspath(args.workdir), "%s.bmp" % name)
            rendered[name] = render(binary, keys, path)
            digests[name] = digest(rendered[name])
        report("ok   the game runs through character creation into the town")

        check_viewport_uses_tiles(rendered["town"], args.assets, report)

        # Determinism: the same seed and the same keys must produce the same
        # screen, or the goldens are meaningless.
        again = render(binary, SCREENS["town"],
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
