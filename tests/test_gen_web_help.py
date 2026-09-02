#!/usr/bin/env python3
"""Tests for tools/gen_web_help.py.

The point of generating the reference from Umoria's own files is that it
cannot drift from the game. That only holds if the parsing is right, and the
race and class tables are positional C initialisers with no field names in
them -- an off-by-one there produces a table that looks entirely plausible and
is wrong. So the values are checked against ones that can be confirmed by
reading the game: a Half-Troll gets 12 hit points, a Dwarf cannot be a Mage.

Usage:
    test_gen_web_help.py --umoria vendored/umoria --template src/web/shell.html
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

import gen_web_help  # noqa: E402

GENERATOR = os.path.join(TOOLS, "gen_web_help.py")

UMORIA = None
TEMPLATE = None


def row_for(page, name):
    """The cells of the reference row whose key column is `name`."""
    match = re.search(r'<tr><td class="key">%s</td>(.*?)</tr>' % re.escape(name),
                      page, re.S)
    if not match:
        return None
    return re.findall(r"<td[^>]*>(.*?)</td>", match.group(1), re.S)


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = os.path.join(cls.tmp.name, "shell.html")
        result = subprocess.run(
            [sys.executable, GENERATOR, "--umoria", UMORIA,
             "--template", TEMPLATE, "--out", cls.out],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        with open(cls.out) as fh:
            cls.page = fh.read()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_placeholder_survives(self):
        self.assertNotIn("<!--COMMANDS-->", self.page)
        self.assertNotIn("<!--RACES_AND_CLASSES-->", self.page)

    def test_the_canvas_and_the_module_hook_are_still_there(self):
        # The template is also the Emscripten shell; losing either would
        # produce a page that renders nothing.
        self.assertIn('id="canvas"', self.page)
        self.assertIn("{{{ SCRIPT }}}", self.page)

    def test_commands_that_matter_are_listed(self):
        for key, description in (("&gt;", "Go down a down-staircase"),
                                 ("&lt;", "Go up an up-staircase"),
                                 ("i", "Inventory list"),
                                 ("M", "Map (shown reduced size)"),
                                 ("?", "View this page")):
            with self.subTest(key=key):
                self.assertRegex(
                    self.page,
                    r'<td class="key">%s</td><td>%s</td>'
                    % (re.escape(key), re.escape(description)))

    def test_a_direction_marker_stays_with_its_key(self):
        # "@ -  ~   Move without pickup" splits awkwardly; the ~ is part of
        # the key, not the description.
        self.assertRegex(self.page,
                         r'<td class="key">@ - ~</td><td>Move without pickup</td>')
        self.assertNotRegex(self.page, r"<td>~\s")

    def test_both_keysets_are_present(self):
        self.assertIn("Original keys", self.page)
        self.assertIn("Roguelike keys", self.page)
        # The roguelike set moves the map to a different key.
        self.assertRegex(self.page, r'<td class="key">P</td><td>Peruse a book</td>')

    def test_race_columns_line_up_with_the_game(self):
        # Half-Troll: +4 str, -4 int, -2 wis, -4 dex, +3 con, -6 chr, 12 hp,
        # 3 ft infravision, 120% experience. Straight out of data_player.cpp.
        cells = row_for(self.page, "Half-Troll")
        self.assertIsNotNone(cells, "no Half-Troll row")
        self.assertEqual(cells[:6], ["+4", "-4", "-2", "-4", "+3", "-6"])
        self.assertEqual(cells[6], "12")
        self.assertEqual(cells[7], "3 ft")
        self.assertEqual(cells[8], "120%")

    def test_a_human_is_the_baseline(self):
        cells = row_for(self.page, "Human")
        self.assertEqual(cells[:6], ["0", "0", "0", "0", "0", "0"])
        self.assertEqual(cells[8], "100%")

    def test_which_classes_a_race_can_take(self):
        # Every class for a Human; Dwarves famously cannot be Mages.
        human = row_for(self.page, "Human")[9]
        for name in ("Warrior", "Mage", "Priest", "Rogue", "Ranger", "Paladin"):
            self.assertIn(name, human)

        dwarf = row_for(self.page, "Dwarf")[9]
        self.assertIn("Warrior", dwarf)
        self.assertIn("Priest", dwarf)
        self.assertNotIn("Mage", dwarf)

    def test_class_columns_line_up_with_the_game(self):
        # Warrior: +5 str, -2 int, -2 wis, +2 dex, +2 con, -1 chr, 9 hp, no
        # spells, no experience penalty.
        cells = row_for(self.page, "Warrior")
        self.assertEqual(cells[:6], ["+5", "-2", "-2", "+2", "+2", "-1"])
        self.assertEqual(cells[6], "9")
        self.assertEqual(cells[7], "none")
        self.assertEqual(cells[8], "+0%")

    def test_spell_lists(self):
        self.assertEqual(row_for(self.page, "Mage")[7], "mage")
        self.assertEqual(row_for(self.page, "Priest")[7], "priest")

    def test_a_moved_field_is_caught(self):
        # The tables are positional, so this is the failure mode worth
        # guarding: shifting a column produces plausible nonsense.
        source = gen_web_help.read(
            os.path.join(UMORIA, "src", "data_player.cpp"))
        races = gen_web_help.parse_table(source, "character_races[")
        self.assertEqual(len(races), 8, "expected eight races")
        self.assertEqual(len(races[0]), 28,
                         "the race initialiser changed shape; the column "
                         "indices in gen_web_help.py need rechecking")


def main():
    global UMORIA, TEMPLATE
    ap = argparse.ArgumentParser()
    ap.add_argument("--umoria", required=True)
    ap.add_argument("--template", required=True)
    args, rest = ap.parse_known_args()
    UMORIA = args.umoria
    TEMPLATE = args.template
    unittest.main(argv=[sys.argv[0], *rest])


if __name__ == "__main__":
    main()
