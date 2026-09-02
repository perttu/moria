#!/usr/bin/env python3
"""Tests for tools/serve.py, the score-keeping server.

The server is written to by a program anyone can edit in the browser's
developer tools, so the checks here are mostly about what it refuses: junk
types, missing fields, oversized bodies, and a torn last line in the history
file. Losing a score is a small thing; serving a broken history, or letting a
malformed post stop the next one being recorded, is not.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, TOOLS)

import serve  # noqa: E402

SERVER = os.path.join(TOOLS, "serve.py")


class CleanTest(unittest.TestCase):
    def test_a_full_record_survives(self):
        record = serve.clean({
            "points": 36, "level": 1, "depth": 0, "deepest_depth": 2,
            "max_hp": 19, "current_hp": 19, "finished": 1788288979,
            "gender": "M", "race": "Human", "class": "Warrior",
            "name": "Fenwick", "died_from": "(saved)",
        })
        self.assertEqual(record["points"], 36)
        self.assertEqual(record["name"], "Fenwick")
        self.assertEqual(record["class"], "Warrior")
        self.assertEqual(record["deepest_depth"], 2)

    def test_missing_fields_become_defaults(self):
        record = serve.clean({})
        for field in serve.NUMERIC_FIELDS:
            self.assertEqual(record[field], 0)
        self.assertEqual(record["name"], "-")
        self.assertEqual(record["race"], "")

    def test_wrong_types_are_replaced_not_stored(self):
        record = serve.clean({
            "points": "a lot", "level": None, "max_hp": True,
            "name": {"not": "a string"}, "race": 7,
        })
        self.assertEqual(record["points"], 0)
        self.assertEqual(record["level"], 0)
        self.assertEqual(record["max_hp"], 0, "a bool is not a score")
        self.assertEqual(record["name"], "-")
        self.assertEqual(record["race"], "")

    def test_unknown_fields_are_dropped(self):
        record = serve.clean({"points": 1, "wizard_mode": True, "cheat": "yes"})
        self.assertNotIn("wizard_mode", record)
        self.assertNotIn("cheat", record)

    def test_text_is_bounded(self):
        record = serve.clean({"name": "x" * 500})
        self.assertEqual(len(record["name"]), serve.MAX_TEXT)

    def test_a_list_is_not_a_score(self):
        with self.assertRaises(ValueError):
            serve.clean([1, 2, 3])


class HistoryFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "scores.jsonl")

    def test_missing_file_is_an_empty_history(self):
        self.assertEqual(serve.read_scores(self.path), [])

    def test_append_then_read(self):
        serve.append_score(self.path, serve.clean({"points": 5, "name": "A"}))
        serve.append_score(self.path, serve.clean({"points": 9, "name": "B"}))
        scores = serve.read_scores(self.path)
        self.assertEqual([s["name"] for s in scores], ["A", "B"])

    def test_a_torn_final_line_costs_only_itself(self):
        # What an interrupted write looks like. The entries before it must
        # still be readable.
        serve.append_score(self.path, serve.clean({"points": 5, "name": "A"}))
        with open(self.path, "a") as fh:
            fh.write('{"points": 9, "na')
        scores = serve.read_scores(self.path)
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0]["name"], "A")


class EndToEndTest(unittest.TestCase):
    """The server as the game actually talks to it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.port = 8123
        with open(os.path.join(cls.tmp.name, "index.html"), "w") as fh:
            fh.write("<h1>moria</h1>")
        cls.process = subprocess.Popen(
            [sys.executable, SERVER, "--dir", cls.tmp.name,
             "--port", str(cls.port)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        for _ in range(50):
            try:
                urllib.request.urlopen(cls.url("/scores"), timeout=1).read()
                return
            except Exception:
                time.sleep(0.1)
        raise AssertionError("the server never came up")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.tmp.cleanup()

    @classmethod
    def url(cls, path):
        return "http://127.0.0.1:%d%s" % (cls.port, path)

    def post(self, payload, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.url("/scores"), data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        return urllib.request.urlopen(request, timeout=5)

    def get(self):
        with urllib.request.urlopen(self.url("/scores"), timeout=5) as response:
            return json.loads(response.read())

    def test_a_posted_game_comes_back(self):
        self.post({"points": 36, "name": "Fenwick", "race": "Human",
                   "class": "Warrior", "level": 1, "died_from": "(saved)"})
        scores = self.get()
        self.assertTrue(any(s["name"] == "Fenwick" and s["points"] == 36
                            for s in scores))

    def test_best_first(self):
        self.post({"points": 1, "name": "Low"})
        self.post({"points": 9999, "name": "High"})
        points = [s["points"] for s in self.get()]
        self.assertEqual(points, sorted(points, reverse=True))

    def test_malformed_json_is_refused_and_does_not_break_the_next_post(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post(None, raw=b"{not json")
        self.assertEqual(caught.exception.code, 400)

        self.post({"points": 7, "name": "After"})
        self.assertTrue(any(s["name"] == "After" for s in self.get()))

    def test_an_oversized_body_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post(None, raw=b"x" * (serve.MAX_BODY + 1))
        self.assertEqual(caught.exception.code, 400)

    def test_the_game_files_are_still_served(self):
        with urllib.request.urlopen(self.url("/index.html"), timeout=5) as r:
            self.assertIn(b"moria", r.read())


if __name__ == "__main__":
    unittest.main()
