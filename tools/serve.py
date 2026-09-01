#!/usr/bin/env python3
"""Serve the browser build, and keep a history of finished games.

This replaces `python3 -m http.server` for the web build: it serves the same
files, and adds two endpoints. Being the same origin as the page means no CORS
and nothing to configure -- the game posts to a relative URL and it arrives
here.

    POST /scores   one finished game, as JSON, from the game itself
    GET  /scores   every game recorded so far, newest first

Scores are appended to a JSON-lines file. Appending rather than rewriting
means an interrupted write can cost at most the last entry, never the
history.

Usage:
    serve.py --dir build-web --port 8080 --scores scores.jsonl
"""

import argparse
import http.server
import json
import os
import socketserver
import sys
import threading

MAX_BODY = 64 * 1024  # a score is a few hundred bytes; this is generous

# What a score record may contain. Anything else is dropped rather than
# stored: this is written to by a program that anyone can edit in devtools.
NUMERIC_FIELDS = ("points", "level", "depth", "deepest_depth", "max_hp",
                  "current_hp", "finished")
TEXT_FIELDS = ("gender", "race", "class", "name", "died_from")
MAX_TEXT = 64

lock = threading.Lock()


def clean(record):
    """Keep the known fields, with sane types and lengths."""
    if not isinstance(record, dict):
        raise ValueError("a score must be a JSON object")

    out = {}
    for field in NUMERIC_FIELDS:
        value = record.get(field, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            value = 0
        out[field] = int(value)
    for field in TEXT_FIELDS:
        value = record.get(field, "")
        if not isinstance(value, str):
            value = ""
        out[field] = value[:MAX_TEXT]
    if not out["name"]:
        out["name"] = "-"
    return out


def read_scores(path):
    if not os.path.exists(path):
        return []
    scores = []
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                scores.append(json.loads(line))
            except ValueError:
                continue  # a torn final line; skip it rather than fail
    return scores


def append_score(path, record):
    with lock:
        with open(path, "a") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


class Handler(http.server.SimpleHTTPRequestHandler):
    scores_path = "scores.jsonl"
    quiet = True

    def log_message(self, *args):
        if not self.quiet:
            super().log_message(*args)

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # The page is served from here, so this is only needed if someone
        # opens the game from a different origin.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/scores") or self.path == "/scores":
            scores = read_scores(self.scores_path)
            scores.sort(key=lambda s: s.get("points", 0), reverse=True)
            self._send_json(200, scores)
            return
        super().do_GET()

    def do_POST(self):
        if not (self.path.rstrip("/").endswith("/scores") or self.path == "/scores"):
            self._send_json(404, {"error": "unknown endpoint"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._send_json(400, {"error": "bad content length"})
            return

        try:
            record = clean(json.loads(self.rfile.read(length)))
        except (ValueError, TypeError) as error:
            self._send_json(400, {"error": str(error)})
            return

        append_score(self.scores_path, record)
        print("moria: recorded %s the %s %s, %d points"
              % (record["name"], record["race"], record["class"],
                 record["points"]), flush=True)
        self._send_json(201, {"stored": True})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="build-web", help="directory to serve")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--scores", default=None,
                    help="the score history file (default: <dir>/scores.jsonl)")
    ap.add_argument("--verbose", action="store_true", help="log every request")
    args = ap.parse_args(argv)

    directory = os.path.abspath(args.dir)
    if not os.path.isdir(directory):
        sys.stderr.write("serve.py: no such directory: %s\n" % directory)
        return 1

    scores_path = args.scores or os.path.join(directory, "scores.jsonl")

    class Bound(Handler):
        pass

    Bound.scores_path = os.path.abspath(scores_path)
    Bound.quiet = not args.verbose

    def build(*handler_args, **handler_kwargs):
        return Bound(*handler_args, directory=directory, **handler_kwargs)

    with Server((args.bind, args.port), build) as httpd:
        print("moria: serving %s on http://localhost:%d/" % (directory, args.port))
        print("moria: scores in %s (%d so far)"
              % (Bound.scores_path, len(read_scores(Bound.scores_path))))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nmoria: stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
