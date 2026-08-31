#!/usr/bin/env python3
"""Extract Henrik Harmsen's GFX_CORR table from amiga_corrlist.c.

The table maps a Moria display code (0-255) to a position in the 8x8 tile
atlas. It is the single most valuable piece of the historical frontend and is
transcribed here mechanically rather than by hand, so the port cannot quietly
drift from the original.

Three things come out of the source file, and all three are required:

  * the explicit assignments -- 230 display codes in Amiga Moria Graphics 1.1;
  * the randomised seeding of all 256 entries that runs first, so that
    hallucination keeps showing graphics instead of falling back to ASCII;
  * the fixup that steps seeded x values out of one band of the atlas.

None of these is optional. A source this tool cannot fully understand is an
error, not something to paper over with defaults: a silently missing fixup
would change which tiles hallucination can show, and nothing downstream would
notice.

The --expect-* options turn the 1.1 values into build-time assertions, so a
substituted or edited source is caught even in a build with tests switched
off.

Usage:
    gen_gfx_corr.py amiga_corrlist.c --hpp amiga_tiles_table.generated.hpp
    gen_gfx_corr.py amiga_corrlist.c --check
"""

import argparse
import re
import sys

# GFX_CORR[x]['@'] = 10 ;   /  GFX_CORR[y][135] = 3;
ASSIGN = re.compile(
    r"GFX_CORR\s*\[\s*(?P<axis>[xy])\s*\]\s*\[\s*(?P<key>'(?:\\.|[^'])'|\d+)\s*\]"
    r"\s*=\s*(?P<value>-?\d+)\s*;")

# cx = randint(33)-1;  /  cy = randint(7)-1;
SEED = re.compile(r"(?P<var>c[xy])\s*=\s*randint\s*\(\s*(?P<range>\d+)\s*\)\s*-\s*1\s*;")

# if ((cx<20) && (cx>13)) cx -= 6;
#
# Written to accept either order of the two comparisons and optional inner
# parentheses, so a semantically identical source does not fall through to
# "no fixup found" and quietly produce a different table.
SEED_FIXUP = re.compile(
    r"if\s*\(\s*\(?\s*cx\s*(?P<op1>[<>])\s*(?P<v1>\d+)\s*\)?"
    r"\s*&&\s*\(?\s*cx\s*(?P<op2>[<>])\s*(?P<v2>\d+)\s*\)?\s*\)"
    r"\s*cx\s*-=\s*(?P<sub>\d+)\s*;")

C_ESCAPES = {
    "\\n": 10, "\\t": 9, "\\r": 13, "\\0": 0, "\\\\": 92, "\\'": 39,
    "\\\"": 34, "\\a": 7, "\\b": 8, "\\f": 12, "\\v": 11,
}


class ExtractError(Exception):
    pass


def parse_key(token):
    if token.isdigit():
        return int(token)
    body = token[1:-1]
    if body in C_ESCAPES:
        return C_ESCAPES[body]
    if len(body) == 1:
        return ord(body)
    raise ExtractError("cannot interpret character literal %r" % token)


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def parse(text):
    text = strip_comments(text)

    xs, ys = {}, {}
    for m in ASSIGN.finditer(text):
        code = parse_key(m.group("key"))
        if not 0 <= code <= 255:
            raise ExtractError("display code %d out of range" % code)
        (xs if m.group("axis") == "x" else ys)[code] = int(m.group("value"))

    if not xs:
        raise ExtractError("no GFX_CORR assignments found")

    missing_pair = sorted(set(xs) ^ set(ys))
    if missing_pair:
        raise ExtractError("display codes assigned on only one axis: %s" % missing_pair)

    seeds = {m.group("var"): int(m.group("range")) for m in SEED.finditer(text)}
    for var in ("cx", "cy"):
        if var not in seeds:
            raise ExtractError(
                "could not find the randomised seeding of %s. init_GFX_CORR() "
                "seeds every entry before assigning the explicit ones; without "
                "it, hallucination would fall back to ASCII." % var)

    fixup = SEED_FIXUP.search(text)
    if fixup is None:
        raise ExtractError(
            "could not find the seed fixup (`if ((cx<20) && (cx>13)) cx -= 6;`). "
            "It keeps seeded entries out of one band of the atlas; defaulting "
            "it away would silently change which tiles hallucination shows.")

    bounds = {fixup.group("op1"): int(fixup.group("v1")),
              fixup.group("op2"): int(fixup.group("v2"))}
    if set(bounds) != {"<", ">"}:
        raise ExtractError(
            "the seed fixup compares cx twice in the same direction (%s); "
            "expected one lower and one upper bound" % fixup.group(0).strip())

    return {
        "tiles": {c: (xs[c], ys[c]) for c in sorted(xs)},
        "seed_x_range": seeds["cx"],
        "seed_y_range": seeds["cy"],
        "seed_fixup": (bounds[">"], bounds["<"], int(fixup.group("sub"))),
    }


def check_expectations(table, args):
    """Compare against the values the 1.1 source is known to carry."""
    tiles = table["tiles"]
    problems = []

    if args.expect_explicit is not None and len(tiles) != args.expect_explicit:
        problems.append("expected %d explicit display codes, found %d"
                        % (args.expect_explicit, len(tiles)))

    if args.expect_extended is not None:
        extended = sum(1 for c in tiles if c > 127)
        if extended != args.expect_extended:
            problems.append("expected %d extended codes above 127, found %d"
                            % (args.expect_extended, extended))

    if args.expect_seed is not None:
        seed = [table["seed_x_range"], table["seed_y_range"]]
        if seed != args.expect_seed:
            problems.append("expected seed ranges %s, found %s"
                            % (args.expect_seed, seed))

    if args.expect_fixup is not None:
        fixup = list(table["seed_fixup"])
        if fixup != args.expect_fixup:
            problems.append("expected seed fixup %s, found %s"
                            % (args.expect_fixup, fixup))

    if args.expect_atlas is not None:
        cols, rows = args.expect_atlas
        outside = {c: xy for c, xy in tiles.items()
                   if xy[0] >= cols or xy[1] >= rows or xy[0] < 0 or xy[1] < 0}
        if outside:
            sample = sorted(outside.items())[:5]
            problems.append("%d display codes map outside a %dx%d atlas, e.g. %s"
                            % (len(outside), cols, rows, sample))
        # A seeded entry must land inside the atlas too, before and after the
        # fixup, or hallucination would sample outside the artwork.
        low, high, sub = table["seed_fixup"]
        seed_max = table["seed_x_range"] - 1
        if seed_max >= cols or table["seed_y_range"] - 1 >= rows:
            problems.append("seed ranges (%d, %d) reach outside a %dx%d atlas"
                            % (table["seed_x_range"], table["seed_y_range"],
                               cols, rows))
        if low - sub < 0:
            problems.append("the seed fixup can produce a negative column")

    return problems


def render_hpp(table, source_name):
    tiles = table["tiles"]
    low, high, sub = table["seed_fixup"]
    rows = "\n".join(
        "    {%3d, %2d, %2d},%s" % (code, x, y, _label(code))
        for code, (x, y) in tiles.items())

    return """// Generated by tools/gen_gfx_corr.py from %s -- do not edit.
//
// Henrik Harmsen's GFX_CORR table: Moria display code -> 8x8 tile atlas cell.
// %d display codes are assigned explicitly; the rest keep the randomised seed
// applied first by init_GFX_CORR(), which is what makes hallucination show
// graphics rather than ASCII.
#pragma once

#include <cstdint>

namespace moria::gfx {

struct TableEntry {
    std::uint8_t code;
    std::uint8_t x;
    std::uint8_t y;
};

// randint(N) in Moria returns 1..N, so the original seed covers 0..N-1.
constexpr int kSeedXRange = %d;
constexpr int kSeedYRange = %d;

// if ((cx < kSeedFixupHigh) && (cx > kSeedFixupLow)) cx -= kSeedFixupSubtract;
constexpr int kSeedFixupLow = %d;
constexpr int kSeedFixupHigh = %d;
constexpr int kSeedFixupSubtract = %d;

inline constexpr TableEntry kGfxCorr[] = {
%s
};

constexpr int kGfxCorrCount = %d;

}  // namespace moria::gfx
""" % (source_name, len(tiles), table["seed_x_range"], table["seed_y_range"],
       low, high, sub, rows, len(tiles))


def _label(code):
    if 33 <= code <= 126:
        ch = chr(code)
        return "  // '%s'" % ("\\'" if ch == "'" else "\\\\" if ch == "\\" else ch)
    if code == 32:
        return "  // ' ' (space)"
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="path to amiga_corrlist.c")
    ap.add_argument("--hpp", help="write the generated header here")
    ap.add_argument("--check", action="store_true",
                    help="print a summary and verify the documented mappings")
    ap.add_argument("--expect-explicit", type=int, metavar="N",
                    help="require exactly N explicitly assigned display codes")
    ap.add_argument("--expect-extended", type=int, metavar="N",
                    help="require exactly N assigned codes above 127")
    ap.add_argument("--expect-seed", type=int, nargs=2, metavar=("X", "Y"),
                    help="require these randint() ranges for cx and cy")
    ap.add_argument("--expect-fixup", type=int, nargs=3,
                    metavar=("LOW", "HIGH", "SUBTRACT"),
                    help="require these seed fixup parameters")
    ap.add_argument("--expect-atlas", type=int, nargs=2, metavar=("COLS", "ROWS"),
                    help="require every mapping to land inside this atlas")
    args = ap.parse_args(argv)

    try:
        with open(args.input, "r", errors="replace") as fh:
            table = parse(fh.read())
    except (ExtractError, OSError) as err:
        sys.stderr.write("%s: %s\n" % (args.input, err))
        return 1

    problems = check_expectations(table, args)
    if problems:
        sys.stderr.write("%s does not match the expected historical source:\n"
                         % args.input)
        for problem in problems:
            sys.stderr.write("  - %s\n" % problem)
        return 1

    tiles = table["tiles"]

    if args.check or not args.hpp:
        print("%s: %d display codes assigned" % (args.input, len(tiles)))
        print("seed: cx in 0..%d, cy in 0..%d, fixup %s"
              % (table["seed_x_range"] - 1, table["seed_y_range"] - 1,
                 table["seed_fixup"]))
        extended = sorted(c for c in tiles if c > 127)
        print("extended codes >127: %d (%s..%s)"
              % (len(extended), extended[0] if extended else "-",
                 extended[-1] if extended else "-"))
        # Mappings quoted in the port brief; a mismatch means we misparsed.
        expected = {ord("@"): (10, 2), ord("."): (20, 1), ord("#"): (13, 2),
                    ord("B"): (2, 1), ord("D"): (2, 3), ord("!"): (12, 4),
                    ord("|"): (6, 6), ord("/"): (8, 6)}
        bad = {chr(c): (tiles.get(c), want) for c, want in expected.items()
               if tiles.get(c) != want}
        if bad:
            sys.stderr.write("MISMATCH against the documented mappings: %s\n" % bad)
            return 1
        print("all %d documented mappings match" % len(expected))

    if args.hpp:
        with open(args.hpp, "w") as fh:
            fh.write(render_hpp(table, args.input.rsplit("/", 1)[-1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
