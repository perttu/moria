#!/usr/bin/env python3
"""Tests for tools/gen_gfx_corr.py, run against the real historical source.

The mutations here are the ones that would otherwise be invisible: a fixup
that stops matching the pattern, a changed seed range, a dropped mapping.
None of them makes a rendered screen look obviously wrong, so the generator
has to be what catches them.

Usage:
    test_gen_gfx_corr.py --corrlist /path/to/amiga_corrlist.c
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, TOOLS)

import gen_gfx_corr  # noqa: E402

GENERATOR = os.path.join(TOOLS, "gen_gfx_corr.py")

# The 1.1 values, as the build asserts them.
EXPECT = ["--expect-explicit", "230", "--expect-extended", "128",
          "--expect-seed", "33", "7", "--expect-fixup", "13", "20", "6",
          "--expect-atlas", "40", "7"]

CORRLIST = None


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CORRLIST, "r", errors="replace") as fh:
            cls.source = fh.read()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hpp = os.path.join(self.tmp.name, "table.generated.hpp")

    def run_on(self, source, extra=()):
        path = os.path.join(self.tmp.name, "amiga_corrlist.c")
        with open(path, "w") as fh:
            fh.write(source)
        return subprocess.run(
            [sys.executable, GENERATOR, path, "--hpp", self.hpp, *EXPECT, *extra],
            capture_output=True, text=True)

    def test_unmodified_source_generates(self):
        result = self.run_on(self.source, extra=["--check"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.exists(self.hpp))
        with open(self.hpp) as fh:
            header = fh.read()
        self.assertIn("kSeedXRange = 33", header)
        self.assertIn("kSeedYRange = 7", header)
        self.assertIn("kSeedFixupLow = 13", header)
        self.assertIn("kSeedFixupHigh = 20", header)
        self.assertIn("kSeedFixupSubtract = 6", header)
        self.assertIn("kGfxCorrCount = 230", header)

    def test_missing_fixup_is_an_error_not_a_default(self):
        mutated = re.sub(r"if\s*\(\s*\(cx<20\)\s*&&\s*\(cx>13\)\s*\)\s*cx\s*-=\s*6\s*;",
                         "", self.source)
        self.assertNotEqual(mutated, self.source, "mutation did not apply")
        result = self.run_on(mutated)
        self.assertNotEqual(result.returncode, 0,
                            "a missing seed fixup must fail, not default to a no-op")
        self.assertIn("seed fixup", result.stderr)
        self.assertFalse(os.path.exists(self.hpp))

    def test_reversed_comparisons_still_match(self):
        # Semantically identical source, written the other way round. This
        # must keep working rather than falling through to "not found".
        mutated = self.source.replace("if ((cx<20) && (cx>13)) cx -= 6;",
                                      "if ((cx>13) && (cx<20)) cx -= 6;")
        self.assertNotEqual(mutated, self.source, "mutation did not apply")
        result = self.run_on(mutated)
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(self.hpp) as fh:
            header = fh.read()
        self.assertIn("kSeedFixupLow = 13", header)
        self.assertIn("kSeedFixupHigh = 20", header)

    def test_changed_seed_range_is_caught(self):
        mutated = self.source.replace("randint(33)", "randint(32)")
        self.assertNotEqual(mutated, self.source, "mutation did not apply")
        result = self.run_on(mutated)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("seed ranges", result.stderr)

    def test_changed_fixup_value_is_caught(self):
        mutated = self.source.replace("cx -= 6;", "cx -= 5;")
        self.assertNotEqual(mutated, self.source, "mutation did not apply")
        result = self.run_on(mutated)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("seed fixup", result.stderr)

    def test_dropped_mapping_is_caught(self):
        mutated = self.source.replace("GFX_CORR[y]['@'] = 2", "// dropped", 1)
        self.assertNotEqual(mutated, self.source, "mutation did not apply")
        result = self.run_on(mutated)
        self.assertNotEqual(result.returncode, 0)

    def test_documented_mappings_are_verified(self):
        mutated = self.source.replace("GFX_CORR[x]['@'] = 10", "GFX_CORR[x]['@'] = 11")
        self.assertNotEqual(mutated, self.source, "mutation did not apply")
        result = self.run_on(mutated, extra=["--check"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISMATCH", result.stderr)

    def test_missing_seeding_is_an_error(self):
        mutated = self.source.replace("cy = randint(7)-1;", "cy = 0;")
        self.assertNotEqual(mutated, self.source, "mutation did not apply")
        result = self.run_on(mutated)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("randomised seeding", result.stderr)

    def test_parse_reports_one_sided_assignments(self):
        mutated = self.source.replace("GFX_CORR[x]['#'] = 13", "GFX_CORR[x][200] = 13")
        with self.assertRaises(gen_gfx_corr.ExtractError):
            gen_gfx_corr.parse(mutated)


def main():
    global CORRLIST
    ap = argparse.ArgumentParser()
    ap.add_argument("--corrlist", required=True)
    args, rest = ap.parse_known_args()
    CORRLIST = args.corrlist
    if not os.path.exists(CORRLIST):
        sys.stderr.write("amiga_corrlist.c not found at %s\n" % CORRLIST)
        return 2
    unittest.main(argv=[sys.argv[0], *rest])


if __name__ == "__main__":
    sys.exit(main())
