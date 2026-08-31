#!/usr/bin/env python3
"""Check that the project builds from a clean tree and that the binary starts.

The pixel tests answer "does it still look like the Amiga". This answers the
question underneath that one: does a fresh checkout configure, compile, and
produce something that actually comes up -- on a real X server as well as
headless -- and exit cleanly.

Two modes:

    build_and_start.py --source . --historical DIR --assets DIR
        configure into a temporary directory, build, then run the start checks

    build_and_start.py --binary path/to/amiga-gfx-test --assets DIR
        run the start checks against a binary that is already built

Usage from the build directory:

    ctest -R smoke-start           # start checks, no rebuild
    cmake -DMORIA_TEST_CLEAN_BUILD=ON ...   # adds build-from-clean
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from compare_screens import read_bmp, SCREENS, SCREEN_WIDTH, SCREEN_HEIGHT  # noqa: E402

BINARY_NAME = "amiga-gfx-test"


class Failure(Exception):
    pass


def run(command, timeout=900, expect_success=True):
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Failure("timed out after %ds: %s" % (timeout, " ".join(command)))
    except FileNotFoundError as err:
        raise Failure("could not run %s: %s" % (command[0], err))

    if expect_success and result.returncode != 0:
        raise Failure("%s exited %d\n--- stdout ---\n%s\n--- stderr ---\n%s"
                      % (" ".join(command), result.returncode,
                         result.stdout.strip(), result.stderr.strip()))
    return result


def configure_and_build(source, build_dir, historical, assets, generator, report):
    command = ["cmake", "--fresh", "-S", source, "-B", build_dir,
               "-DCMAKE_BUILD_TYPE=Release",
               "-DMORIA_HISTORICAL_DIR=%s" % historical,
               "-DMORIA_ASSET_DIR=%s" % assets]
    if generator:
        command += ["-G", generator]
    run(command)
    report("ok   configures from a clean cache")

    jobs = str(os.cpu_count() or 1)
    run(["cmake", "--build", build_dir, "-j", jobs, "--target", BINARY_NAME])
    report("ok   builds %s" % BINARY_NAME)

    binary = os.path.join(build_dir, BINARY_NAME)
    if not os.path.exists(binary):
        # Multi-config generators put it in a subdirectory.
        for config in ("Release", "Debug"):
            candidate = os.path.join(build_dir, config, BINARY_NAME)
            if os.path.exists(candidate):
                binary = candidate
                break
    if not os.path.exists(binary):
        raise Failure("the build produced no %s" % BINARY_NAME)
    if not os.access(binary, os.X_OK):
        raise Failure("%s is not executable" % binary)
    report("ok   produced an executable at %s" % binary)
    return binary


def check_starts(binary, workdir, report):
    result = run([binary, "--help"])
    if "usage:" not in result.stdout:
        raise Failure("--help printed no usage text")
    report("ok   starts and prints usage for --help")

    result = run([binary, "--screen", "nonsense"], expect_success=False)
    if result.returncode == 0:
        raise Failure("an unknown screen name was accepted")
    report("ok   rejects a bad argument instead of starting")

    for screen in SCREENS:
        shot = os.path.join(workdir, "start-%s.bmp" % screen)
        run([binary, "--headless", "--screen", screen, "--screenshot", shot],
            timeout=120)
        width, height, _rows = read_bmp(shot)
        if (width, height) != (SCREEN_WIDTH, SCREEN_HEIGHT):
            raise Failure("%s screen rendered %dx%d, expected %dx%d"
                          % (screen, width, height, SCREEN_WIDTH, SCREEN_HEIGHT))
    report("ok   opens and renders all %d screens headlessly at %dx%d"
           % (len(SCREENS), SCREEN_WIDTH, SCREEN_HEIGHT))

    # Scaling is the one thing that differs between "it ran" and "it opened a
    # window the right size", so exercise a non-default scale too.
    shot = os.path.join(workdir, "start-scaled.bmp")
    run([binary, "--headless", "--scale", "3", "--screen", "dungeon",
         "--screenshot", shot], timeout=120)
    width, height, _rows = read_bmp(shot)
    if (width, height) != (SCREEN_WIDTH, SCREEN_HEIGHT):
        raise Failure("at --scale 3 the virtual screen became %dx%d; it must "
                      "stay %dx%d and only the window should grow"
                      % (width, height, SCREEN_WIDTH, SCREEN_HEIGHT))
    report("ok   --scale 3 leaves the virtual screen at %dx%d"
           % (SCREEN_WIDTH, SCREEN_HEIGHT))

    if shutil.which("xvfb-run") is None:
        report("skip real-window start: xvfb-run is not installed")
        return
    shot = os.path.join(workdir, "start-x11.bmp")
    run(["xvfb-run", "-a", binary, "--screen", "dungeon", "--screenshot", shot],
        timeout=120)
    width, height, _rows = read_bmp(shot)
    if (width, height) != (SCREEN_WIDTH, SCREEN_HEIGHT):
        raise Failure("the X11 window render was %dx%d" % (width, height))
    report("ok   starts against a real X server, not just the dummy driver")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", help="source tree to configure (enables the build check)")
    ap.add_argument("--binary", help="an already-built amiga-gfx-test to check")
    ap.add_argument("--historical", help="directory containing amiga_corrlist.c")
    ap.add_argument("--assets", required=True, help="directory containing the .iff files")
    ap.add_argument("--build", help="build directory to use (default: a temporary one)")
    ap.add_argument("--generator", help="CMake generator, e.g. Ninja")
    ap.add_argument("--keep", action="store_true", help="keep the temporary build tree")
    args = ap.parse_args(argv)

    if not args.source and not args.binary:
        ap.error("give --source to build, or --binary to check an existing build")
    if args.source and not args.historical:
        ap.error("--source requires --historical")

    lines = []

    def report(line):
        lines.append(line)
        print(line, flush=True)

    temp = None
    try:
        if args.source:
            build_dir = args.build
            if not build_dir:
                temp = tempfile.mkdtemp(prefix="moria-build-")
                build_dir = temp
            binary = configure_and_build(args.source, build_dir, args.historical,
                                         args.assets, args.generator, report)
        else:
            binary = args.binary
            if not os.path.exists(binary):
                raise Failure("no binary at %s" % binary)
            report("ok   found %s" % binary)

        with tempfile.TemporaryDirectory() as workdir:
            check_starts(binary, workdir, report)
    except Failure as err:
        print("\nFAIL %s" % err, file=sys.stderr)
        return 1
    finally:
        if temp and not args.keep:
            shutil.rmtree(temp, ignore_errors=True)

    print("\nit builds and it starts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
