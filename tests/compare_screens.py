#!/usr/bin/env python3
"""Pixel regression tests for the 640x200 framebuffer.

Running the binary and getting a file out proves only that the process did not
crash. These checks look at the pixels:

  * the three atlases still have the geometry the frontend assumes;
  * the rendered title screen is pixel-identical to moria_title.iff;
  * specific dungeon cells hold the exact atlas tile for their display code at
    the exact screen position the Amiga put them, so a shifted viewport origin
    fails even if the goldens were regenerated;
  * every deterministic screen matches a reviewed golden hash;
  * the X11 path and the headless software path agree byte for byte.

Usage:
    compare_screens.py --binary build/amiga-gfx-test --assets /path/to/Moria \\
        --workdir build/screens --golden tests/golden_screens.json
    ... --update    to rewrite the goldens after reviewing the new images
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, TOOLS)

import iff_convert  # noqa: E402

SCREENS = ("title", "tiles", "dungeon", "overview")

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 200
CELL = 8

# From amiga.c: mvaddchg() indexes screen[col - 13][row - 1].
MAP_COL_OFFSET = 13
MAP_ROW_OFFSET = 1

# The title screen's own caption, drawn by the test app rather than by Henrik.
TITLE_CAPTION_ROW = 23

EXPECTED_GEOMETRY = {
    "moria_gfx": (320, 56),
    "moria_gfxsmall": (80, 14),
    "moria_title": (640, 200),
}

# Cells the stand-in level places at known map coordinates, and the atlas
# position GFX_CORR gives their display code.
DUNGEON_CELLS = (
    ("player '@'", 8, 8, (10, 2)),
    ("wall '#'", 2, 2, (13, 2)),
)


class Failure(Exception):
    pass


def read_bmp(path):
    """Read the 24-bit bottom-up BMP that save_screenshot() writes."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:2] != b"BM":
        raise Failure("%s is not a BMP" % path)
    pixel_offset = struct.unpack("<I", data[10:14])[0]
    header_size = struct.unpack("<I", data[14:18])[0]
    if header_size < 40:
        raise Failure("%s has an unsupported BMP header" % path)
    width, height, planes, bpp = struct.unpack("<iiHH", data[18:30])
    compression = struct.unpack("<I", data[30:34])[0]
    if planes != 1 or bpp != 24 or compression != 0:
        raise Failure("%s is %d bpp, compression %d; expected uncompressed 24 bpp"
                      % (path, bpp, compression))

    bottom_up = height > 0
    height = abs(height)
    stride = ((width * 3) + 3) & ~3
    rows = []
    for y in range(height):
        src = y if not bottom_up else (height - 1 - y)
        start = pixel_offset + src * stride
        row = data[start:start + width * 3]
        # BMP stores BGR.
        rows.append(bytes(b for i in range(0, len(row), 3)
                          for b in (row[i + 2], row[i + 1], row[i])))
    return width, height, rows


def load_iff(assets_dir, name):
    with open(os.path.join(assets_dir, "%s.iff" % name), "rb") as fh:
        return iff_convert.parse_ilbm(fh.read())


def rgb_rows(image):
    """The image as a list of RGB byte-rows, alpha forced opaque.

    The renderer is fed opaque arrays, because putgfx() copies every bitplane
    rather than honouring the mask.
    """
    rgba = image.rgba(opaque=True)
    out = []
    for y in range(image.height):
        start = y * image.width * 4
        row = rgba[start:start + image.width * 4]
        out.append(bytes(b for i in range(0, len(row), 4)
                         for b in row[i:i + 3]))
    return out


def digest(rows):
    h = hashlib.sha256()
    for row in rows:
        h.update(row)
    return h.hexdigest()


def render(binary, screen, out_path, xvfb=False):
    command = [binary, "--screen", screen, "--screenshot", out_path]
    if xvfb:
        command = ["xvfb-run", "-a", *command]
    else:
        command.append("--headless")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise Failure("rendering %s failed: %s%s"
                      % (screen, result.stdout, result.stderr))
    if not os.path.exists(out_path):
        raise Failure("rendering %s wrote no file" % screen)
    return read_bmp(out_path)


def check_geometry(assets_dir, report):
    for name, (want_w, want_h) in EXPECTED_GEOMETRY.items():
        image = load_iff(assets_dir, name)
        if (image.width, image.height) != (want_w, want_h):
            raise Failure("%s.iff is %dx%d, expected %dx%d"
                          % (name, image.width, image.height, want_w, want_h))
        report("ok   %s.iff is %dx%d, %d planes, masking %d"
               % (name, image.width, image.height, image.planes, image.masking))


def check_title(rendered, assets_dir, report):
    width, height, rows = rendered
    if (width, height) != (SCREEN_WIDTH, SCREEN_HEIGHT):
        raise Failure("title render is %dx%d, expected %dx%d"
                      % (width, height, SCREEN_WIDTH, SCREEN_HEIGHT))

    original = rgb_rows(load_iff(assets_dir, "moria_title"))
    caption_first = TITLE_CAPTION_ROW * CELL
    caption_last = caption_first + CELL

    differing = 0
    first_difference = None
    for y in range(SCREEN_HEIGHT):
        if caption_first <= y < caption_last:
            continue
        if rows[y] == original[y]:
            continue
        for x in range(SCREEN_WIDTH):
            if rows[y][x * 3:x * 3 + 3] != original[y][x * 3:x * 3 + 3]:
                differing += 1
                if first_difference is None:
                    first_difference = (x, y, rows[y][x * 3:x * 3 + 3],
                                        original[y][x * 3:x * 3 + 3])

    if differing:
        raise Failure(
            "the rendered title differs from moria_title.iff in %d pixels; "
            "first at x=%d y=%d, rendered %s, original %s"
            % (differing, *first_difference))
    report("ok   title is pixel-identical to moria_title.iff outside row %d"
           % TITLE_CAPTION_ROW)


def check_dungeon_cells(rendered, assets_dir, report):
    _width, _height, rows = rendered
    atlas = rgb_rows(load_iff(assets_dir, "moria_gfx"))

    for label, map_x, map_y, (tile_x, tile_y) in DUNGEON_CELLS:
        screen_x = (MAP_COL_OFFSET + map_x) * CELL
        screen_y = (MAP_ROW_OFFSET + map_y) * CELL
        for row in range(CELL):
            want = atlas[tile_y * CELL + row][tile_x * CELL * 3:
                                              (tile_x * CELL + CELL) * 3]
            got = rows[screen_y + row][screen_x * 3:(screen_x + CELL) * 3]
            if got != want:
                raise Failure(
                    "%s is not drawn at column %d, row %d: scanline %d of that "
                    "cell does not match atlas tile (%d, %d)"
                    % (label, MAP_COL_OFFSET + map_x, MAP_ROW_OFFSET + map_y,
                       row, tile_x, tile_y))
        report("ok   %s is the exact atlas tile at column %d, row %d"
               % (label, MAP_COL_OFFSET + map_x, MAP_ROW_OFFSET + map_y))


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

    for screen in SCREENS:
        if screen not in golden:
            raise Failure("no golden recorded for the %s screen" % screen)
        if golden[screen] != digests[screen]:
            raise Failure("the %s screen changed: golden %s, rendered %s"
                          % (screen, golden[screen][:16], digests[screen][:16]))
        report("ok   %s matches its golden" % screen)


def check_x11_matches_headless(binary, workdir, report):
    if shutil.which("xvfb-run") is None:
        report("skip X11 comparison: xvfb-run is not installed")
        return
    try:
        x11 = render(binary, "dungeon", os.path.join(workdir, "x11-dungeon.bmp"),
                     xvfb=True)
    except Failure as err:
        report("skip X11 comparison: %s" % err)
        return
    headless = read_bmp(os.path.join(workdir, "dungeon.bmp"))
    if x11[2] != headless[2]:
        raise Failure("the X11 render and the headless render differ; the "
                      "screenshots taken in CI are not the pixels a player sees")
    report("ok   the X11 render is byte-identical to the headless render")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--binary", required=True, help="path to amiga-gfx-test")
    ap.add_argument("--assets", required=True, help="directory holding the .iff files")
    ap.add_argument("--workdir", required=True, help="where to write renders")
    ap.add_argument("--golden", required=True, help="golden hash file")
    ap.add_argument("--update", action="store_true",
                    help="rewrite the goldens instead of comparing")
    args = ap.parse_args(argv)

    os.makedirs(args.workdir, exist_ok=True)
    lines = []

    def report(line):
        lines.append(line)
        print(line)

    try:
        check_geometry(args.assets, report)

        rendered = {}
        digests = {}
        for screen in SCREENS:
            rendered[screen] = render(args.binary, screen,
                                      os.path.join(args.workdir, "%s.bmp" % screen))
            digests[screen] = digest(rendered[screen][2])

        check_title(rendered["title"], args.assets, report)
        check_dungeon_cells(rendered["dungeon"], args.assets, report)
        check_goldens(digests, args.golden, args.update, report)
        check_x11_matches_headless(args.binary, args.workdir, report)
    except Failure as err:
        print("\nFAIL %s" % err, file=sys.stderr)
        return 1

    print("\nall pixel checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
