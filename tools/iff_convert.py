#!/usr/bin/env python3
"""Convert an Amiga IFF ILBM file to a PNG and/or an embeddable C++ array.

This is a one-way container change. Dimensions, pixels, palette and tile
positions are preserved exactly; nothing is resampled, reordered or
recoloured. The original .iff remains the authoritative artefact.

Usage:
    iff_convert.py IN.iff --png OUT.png
    iff_convert.py IN.iff --cpp OUT.cpp --hpp OUT.hpp --name moria_gfx
    iff_convert.py IN.iff --info

No third-party dependencies: PNG output is written with zlib directly so the
tool runs anywhere a stock Python 3 does.
"""

import argparse
import struct
import sys
import zlib


class IffError(Exception):
    pass


class Ilbm:
    def __init__(self, width, height, planes, palette, indices):
        self.width = width
        self.height = height
        self.planes = planes
        self.palette = palette  # list of (r, g, b)
        self.indices = indices  # bytearray, width * height palette indices

    def rgba(self):
        """Flatten to RGBA8888 bytes, opaque."""
        out = bytearray(self.width * self.height * 4)
        pal = self.palette
        for i, idx in enumerate(self.indices):
            r, g, b = pal[idx] if idx < len(pal) else (0, 0, 0)
            o = i * 4
            out[o] = r
            out[o + 1] = g
            out[o + 2] = b
            out[o + 3] = 255
        return bytes(out)


def _chunks(data):
    if data[0:4] != b"FORM":
        raise IffError("not an IFF FORM file")
    if data[8:12] != b"ILBM":
        raise IffError("IFF file is not an ILBM (got %r)" % data[8:12])
    pos = 12
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        yield cid, data[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)  # chunks are word aligned


def _unpack_byterun1(src, expected):
    """Decode ByteRun1 (compression 1) into exactly `expected` bytes."""
    out = bytearray()
    i = 0
    n = len(src)
    while len(out) < expected:
        if i >= n:
            raise IffError("BODY ran out while unpacking ByteRun1")
        ctl = src[i]
        i += 1
        if ctl == 128:
            continue  # no-op
        if ctl < 128:
            count = ctl + 1
            out += src[i:i + count]
            i += count
        else:
            count = 257 - ctl
            out += bytes([src[i]]) * count
            i += 1
    return bytes(out[:expected]), i


def parse_ilbm(data):
    header = None
    palette = []
    body = None
    for cid, payload in _chunks(data):
        if cid == b"BMHD":
            header = struct.unpack(">HHhhBBBBHBBhh", payload[:20])
        elif cid == b"CMAP":
            palette = [tuple(payload[i:i + 3]) for i in range(0, len(payload) - 2, 3)]
        elif cid == b"BODY":
            body = payload
    if header is None:
        raise IffError("no BMHD chunk")
    if body is None:
        raise IffError("no BODY chunk")

    width, height, _x, _y, planes, masking, compression, _pad = header[:8]
    if compression not in (0, 1):
        raise IffError("unsupported compression %d" % compression)

    row_bytes = ((width + 15) // 16) * 2
    # masking == 1 stores a 1-bit mask plane after the colour planes
    total_planes = planes + (1 if masking == 1 else 0)

    if compression == 1:
        raw, _used = _unpack_byterun1(body, row_bytes * total_planes * height)
    else:
        raw = body

    indices = bytearray(width * height)
    pos = 0
    for y in range(height):
        base = y * width
        for p in range(total_planes):
            row = raw[pos:pos + row_bytes]
            pos += row_bytes
            if p >= planes:
                continue  # mask plane: not part of the colour index
            bit = 1 << p
            for x in range(width):
                if row[x >> 3] & (0x80 >> (x & 7)):
                    indices[base + x] |= bit

    if not palette:
        # Greyscale ramp so a CMAP-less file still converts rather than failing.
        levels = 1 << planes
        palette = [(i * 255 // max(1, levels - 1),) * 3 for i in range(levels)]

    return Ilbm(width, height, planes, palette, indices)


def write_png(path, image):
    """Write an indexed (colour type 3) PNG, preserving the palette exactly."""

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    w, h = image.width, image.height
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0 (None) keeps indices byte-for-byte
        raw += image.indices[y * w:(y + 1) * w]

    plte = b"".join(bytes(c) for c in image.palette)
    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0))
    out += chunk(b"PLTE", plte)
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(out)


def _c_array(name, data, per_line=16):
    lines = ["const unsigned char %s[%d] = {" % (name, len(data))]
    for i in range(0, len(data), per_line):
        lines.append("    " + "".join("0x%02X," % b for b in data[i:i + per_line]))
    lines.append("};")
    return "\n".join(lines)


def write_cpp(cpp_path, hpp_path, name, image, source_name):
    guard_include = hpp_path.rsplit("/", 1)[-1] if hpp_path else ""

    # The Image struct itself is hand-written in src/frontend/moria_assets.hpp
    # so that several generated headers can be included together.
    hpp = """// Generated by tools/iff_convert.py from %s -- do not edit.
#pragma once

#include "moria_assets.hpp"

namespace moria::assets {

extern const Image %s;

}  // namespace moria::assets
""" % (source_name, name)

    cpp = """// Generated by tools/iff_convert.py from %s -- do not edit.
// %dx%d, %d bitplanes, %d palette entries. Pixels are unmodified.
#include "%s"

namespace moria::assets {
namespace {

%s

}  // namespace

const Image %s = {%d, %d, %s_pixels};

}  // namespace moria::assets
""" % (source_name, image.width, image.height, image.planes, len(image.palette),
       guard_include, _c_array("%s_pixels" % name, image.rgba()), name,
       image.width, image.height, name)

    if hpp_path:
        with open(hpp_path, "w") as fh:
            fh.write(hpp)
    if cpp_path:
        with open(cpp_path, "w") as fh:
            fh.write(cpp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="source .iff (ILBM) file")
    ap.add_argument("--png", help="write an indexed PNG here")
    ap.add_argument("--cpp", help="write an embeddable C++ source here")
    ap.add_argument("--hpp", help="write the matching C++ header here")
    ap.add_argument("--name", help="C++ identifier for the image")
    ap.add_argument("--info", action="store_true", help="print header details")
    args = ap.parse_args(argv)

    with open(args.input, "rb") as fh:
        image = parse_ilbm(fh.read())

    if args.info or not (args.png or args.cpp or args.hpp):
        print("%s: %dx%d, %d planes, %d colours"
              % (args.input, image.width, image.height, image.planes, len(image.palette)))
        print("palette: " + " ".join("#%02X%02X%02X" % c for c in image.palette))

    if args.png:
        write_png(args.png, image)
    if args.cpp or args.hpp:
        if not args.name:
            ap.error("--cpp/--hpp require --name")
        write_cpp(args.cpp, args.hpp, args.name, image, args.input.rsplit("/", 1)[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
