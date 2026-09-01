#!/usr/bin/env python3
"""Build the browser page, with reference panels generated from the game.

Moria expects you to know about forty single-key commands, and to have read a
manual before choosing a race and a class. On the Amiga that was what the
printed docs were for. In a browser the reference can simply sit next to the
game.

Everything here is generated from Umoria's own files rather than written by
hand -- the command lists out of data/help.txt and data/rl_help.txt, the race
and class tables out of data_player.cpp -- so the reference cannot drift away
from the game it describes. If upstream adds a command or rebalances a class,
this follows.

Usage:
    gen_web_help.py --umoria vendored/umoria --template src/web/shell.html \\
        --out build/shell.generated.html
"""

import argparse
import html
import os
import re
import sys

# Race_t and Class_t, from src/character.h. Only the fields worth showing when
# you are choosing are named; the rest are skipped positionally.
RACE_FIELDS = ["str", "int", "wis", "dex", "con", "chr"]
# Verified against the literals rather than counted off the struct comments:
# for Human these are 10 hit points, no infravision, 100% experience, and
# 0x3F -- all six classes allowed.
RACE_HIT_POINTS = 24   # hit_points_base
RACE_INFRA = 25        # infra_vision
RACE_EXP = 26          # exp_factor_base
RACE_CLASSES = 27      # classes_bit_field

CLASS_HIT_POINTS = 1
CLASS_STATS = slice(9, 15)   # str, int, wis, dex, con, chr
CLASS_SPELL = 15
CLASS_EXP = 16


class GenerateError(Exception):
    pass


def read(path):
    with open(path, "r", errors="replace") as fh:
        return fh.read()


def parse_table(source, marker):
    """The rows of a brace-initialised C array, as lists of raw fields."""
    start = source.find(marker)
    if start < 0:
        raise GenerateError("could not find %s" % marker)
    body = source[source.index("{", start) + 1:]

    rows = []
    depth = 0
    current = ""
    for char in body:
        if char == "{":
            depth += 1
            if depth == 1:
                current = ""
                continue
        elif char == "}":
            depth -= 1
            if depth == 0:
                rows.append(current)
                continue
            if depth < 0:
                break
        if depth >= 1:
            current += char

    parsed = []
    for row in rows:
        fields = [f.strip() for f in row.split(",")]
        fields = [f for f in fields if f != ""]
        if fields and fields[0].startswith('"'):
            parsed.append(fields)
    return parsed


def unquote(field):
    return field.strip().strip('"')


def signed(value):
    try:
        number = int(value)
    except ValueError:
        return html.escape(value)
    return "+%d" % number if number > 0 else str(number)


def command_rows(text):
    """Split help.txt's two-column layout back into single commands."""
    rows = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        for half in line.split("|"):
            half = half.rstrip()
            if not half.strip():
                continue
            # "@ B ~      Bash item or monster" -- keys, then description.
            match = re.match(r"\s*(.{1,10}?)\s{2,}(\S.*)$", half)
            if not match:
                continue
            key = match.group(1).strip()
            description = match.group(2).strip()
            # "@ -  ~    Move without pickup" splits at the first run of
            # spaces, leaving the direction marker at the front of the
            # description. It belongs with the key.
            if description.startswith("~"):
                key = (key + " ~").strip()
                description = description[1:].strip()
            rows.append((key, description))
    return rows


def preamble(text):
    """The prose around the table, as a heading line and the rest.

    help.txt is a fixed-width page: a title, the command grid, a direction
    diagram, then several paragraphs hard-wrapped to the terminal. The wrapped
    lines are rejoined so the browser can lay them out, and the diagram is
    kept as a block because its shape is the point.
    """
    lines = [line for line in text.splitlines() if "|" not in line]

    diagram = []
    prose = []
    paragraph = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if paragraph:
                prose.append(paragraph)
                paragraph = ""
            continue
        # The direction diagram is short, mostly digits or movement letters.
        if len(stripped) <= 24 and not stripped.endswith("."):
            if paragraph:
                prose.append(paragraph)
                paragraph = ""
            diagram.append(stripped)
            continue
        paragraph = (paragraph + " " + stripped).strip()
    if paragraph:
        prose.append(paragraph)

    return diagram, prose


def render_commands(umoria):
    sections = []
    for filename, title in (("help.txt", "Original keys"),
                            ("rl_help.txt", "Roguelike keys")):
        path = os.path.join(umoria, "data", filename)
        if not os.path.exists(path):
            continue
        text = read(path)
        rows = command_rows(text)
        if not rows:
            raise GenerateError("no commands parsed from %s" % filename)
        body = "\n".join(
            '        <tr><td class="key">%s</td><td>%s</td></tr>'
            % (html.escape(key), html.escape(description))
            for key, description in sorted(rows, key=lambda r: r[1].lower()))

        diagram, prose = preamble(text)
        # The table first: it is what you came for. The manual's prose folds
        # away underneath.
        notes = ""
        if diagram:
            notes += ('      <pre class="diagram">%s</pre>\n'
                      % html.escape("\n".join(diagram)))
        if prose:
            notes += ('      <details><summary>Notes</summary>\n%s\n'
                      '      </details>\n'
                      % "\n".join("        <p>%s</p>" % html.escape(p)
                                  for p in prose))
        sections.append(
            '    <section>\n      <h3>%s</h3>\n'
            '      <table class="reference">\n%s\n      </table>\n%s    </section>'
            % (html.escape(title), body, notes))
    return "\n".join(sections)


def render_races_and_classes(umoria):
    source = read(os.path.join(umoria, "src", "data_player.cpp"))
    races = parse_table(source, "character_races[")
    classes = parse_table(source, "classes[")
    if not races or not classes:
        raise GenerateError("could not parse the race or class tables")

    class_names = [unquote(row[0]) for row in classes]

    race_rows = []
    for row in races:
        allowed = []
        try:
            mask = int(row[RACE_CLASSES], 0)
        except (ValueError, IndexError):
            mask = 0
        for index, name in enumerate(class_names):
            if mask & (1 << index):
                allowed.append(name)
        race_rows.append(
            '        <tr><td class="key">%s</td>%s<td>%s</td><td>%s</td>'
            '<td>%s</td><td>%s</td></tr>'
            % (html.escape(unquote(row[0])),
               "".join("<td>%s</td>" % signed(row[1 + i])
                       for i in range(len(RACE_FIELDS))),
               html.escape(row[RACE_HIT_POINTS]),
               html.escape(row[RACE_INFRA]) + " ft",
               html.escape(row[RACE_EXP]) + "%",
               html.escape(", ".join(allowed) if allowed else "-")))

    spell_names = {"SPELL_TYPE_NONE": "none", "SPELL_TYPE_MAGE": "mage",
                   "SPELL_TYPE_PRIEST": "priest"}
    class_rows = []
    for row in classes:
        spell = row[CLASS_SPELL].rsplit("::", 1)[-1]
        class_rows.append(
            '        <tr><td class="key">%s</td>%s<td>%s</td><td>%s</td>'
            '<td>%s</td></tr>'
            % (html.escape(unquote(row[0])),
               "".join("<td>%s</td>" % signed(value)
                       for value in row[CLASS_STATS]),
               html.escape(row[CLASS_HIT_POINTS]),
               html.escape(spell_names.get(spell, spell)),
               "+" + html.escape(row[CLASS_EXP]) + "%"))

    stat_headers = "".join("<th>%s</th>" % name.upper() for name in RACE_FIELDS)
    return """    <section>
      <h3>Races</h3>
      <p>Stat adjustments, extra hit points per level, infravision, and the
         experience each race needs relative to a Human.</p>
      <table class="reference">
        <tr><th>Race</th>%s<th>HP</th><th>Infra</th><th>Exp</th>
            <th>Can be</th></tr>
%s
      </table>
    </section>
    <section>
      <h3>Classes</h3>
      <p>Stat adjustments, extra hit points per level, which spell list they
         use, and the experience penalty on top of the race's.</p>
      <table class="reference">
        <tr><th>Class</th>%s<th>HP</th><th>Spells</th><th>Exp</th></tr>
%s
      </table>
    </section>""" % (stat_headers, "\n".join(race_rows),
                     stat_headers, "\n".join(class_rows))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--umoria", required=True, help="the Umoria source tree")
    ap.add_argument("--template", required=True, help="the page template")
    ap.add_argument("--out", required=True, help="the page to write")
    args = ap.parse_args(argv)

    try:
        page = read(args.template)
        page = page.replace("<!--COMMANDS-->", render_commands(args.umoria))
        page = page.replace("<!--RACES_AND_CLASSES-->",
                            render_races_and_classes(args.umoria))
    except (GenerateError, OSError) as err:
        sys.stderr.write("gen_web_help.py: %s\n" % err)
        return 1

    for placeholder in ("<!--COMMANDS-->", "<!--RACES_AND_CLASSES-->"):
        if placeholder in page:
            sys.stderr.write("gen_web_help.py: %s was not filled in\n" % placeholder)
            return 1

    with open(args.out, "w") as fh:
        fh.write(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
