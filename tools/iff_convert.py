#!/usr/bin/env python3
"""Convert an Amiga IFF ILBM file to a PNG and/or an embeddable C++ array.

This is a one-way container change. Dimensions, pixels, palette and tile
positions are preserved exactly; nothing is resampled, reordered or
recoloured. The original .iff remains the authoritative artefact.

Transparency is decoded rather than discarded. Both tile atlases in the 1.2
distribution declare masking mode 2 with transparentColor 0, so dropping it
would quietly turn a documented property of the artwork into opaque black.

Rendering is a separate question from conversion: putgfx() in amiga.c copies
all four bitplanes unconditionally, so on the Amiga a tile's colour 0 is drawn
as black, not as a hole. Pass --opaque to reproduce that when generating the
arrays the renderer uses.

Usage:
    iff_convert.py IN.iff --png OUT.png
    iff_convert.py IN.iff --cpp OUT.cpp --hpp OUT.hpp --name moria_gfx
    iff_convert.py IN.iff --info

No third-party dependencies: PNG output is written with zlib directly so the
tool runs anywhere a stock Python 3 does.
"""

import argparse
import re
import struct
import sys
import zlib

MASK_NONE = 0
MASK_PLANE = 1
MASK_TRANSPARENT_COLOR = 2
MASK_LASSO = 3

C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class IffError(Exception):
    pass


class Ilbm:
    def __init__(self, width, height, planes, palette, indices, alpha, masking,
                 transparent_color):
        self.width = width
        self.height = height
        self.planes = planes
        self.palette = palette  # list of (r, g, b)
        self.indices = indices  # bytearray, width * height palette indices
        self.alpha = alpha      # bytearray, width * height, 0 or 255
        self.masking = masking
        self.transparent_color = transparent_color

    @property
    def has_transparency(self):
        return any(a == 0 for a in self.alpha)

    def rgba(self, opaque=False):
        """Flatten to RGBA8888 bytes."""
        out = bytearray(self.width * self.height * 4)
        pal = self.palette
        for i, idx in enumerate(self.indices):
            r, g, b = pal[idx] if idx < len(pal) else (0, 0, 0)
            o = i * 4
            out[o] = r
            out[o + 1] = g
            out[o + 2] = b
            out[o + 3] = 255 if opaque else self.alpha[i]
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
            if len(payload) < 20:
                raise IffError("BMHD chunk is truncated")
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
    transparent_color = header[8]

    if compression not in (0, 1):
        raise IffError("unsupported compression %d" % compression)
    if masking not in (MASK_NONE, MASK_PLANE, MASK_TRANSPARENT_COLOR):
        # Lasso masking needs a bounding box we do not carry, and anything
        # else is not ILBM. Refuse rather than guess.
        raise IffError("unsupported masking mode %d" % masking)
    if planes < 1 or planes > 8:
        raise IffError("unsupported bitplane count %d" % planes)

    row_bytes = ((width + 15) // 16) * 2
    total_planes = planes + (1 if masking == MASK_PLANE else 0)

    if compression == 1:
        raw, _used = _unpack_byterun1(body, row_bytes * total_planes * height)
    else:
        needed = row_bytes * total_planes * height
        if len(body) < needed:
            raise IffError("BODY holds %d bytes, expected %d" % (len(body), needed))
        raw = body

    indices = bytearray(width * height)
    alpha = bytearray(b"\xFF" * (width * height))
    pos = 0
    for y in range(height):
        base = y * width
        for p in range(total_planes):
            row = raw[pos:pos + row_bytes]
            pos += row_bytes
            is_mask = (p >= planes)
            bit = 1 << p
            for x in range(width):
                if not (row[x >> 3] & (0x80 >> (x & 7))):
                    if is_mask:
                        # A clear bit in the mask plane means transparent.
                        alpha[base + x] = 0
                    continue
                if not is_mask:
                    indices[base + x] |= bit

    if masking == MASK_TRANSPARENT_COLOR:
        for i, idx in enumerate(indices):
            if idx == transparent_color:
                alpha[i] = 0

    if not palette:
        # Greyscale ramp so a CMAP-less file still converts rather than failing.
        levels = 1 << planes
        palette = [(i * 255 // max(1, levels - 1),) * 3 for i in range(levels)]

    return Ilbm(width, height, planes, palette, indices, alpha, masking,
                transparent_color)


def _chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def write_png(path, image):
    """Write a PNG that carries the same transparency the ILBM declared.

    Masking by transparent colour stays indexed with a tRNS chunk, which is
    exactly the same idea in PNG's vocabulary. An arbitrary per-pixel mask
    plane cannot be expressed that way, so those become RGBA.
    """
    w, h = image.width, image.height
    out = b"\x89PNG\r\n\x1a\n"

    if image.masking == MASK_PLANE and image.has_transparency:
        rgba = image.rgba()
        raw = bytearray()
        for y in range(h):
            raw.append(0)  # filter type 0 (None)
            raw += rgba[y * w * 4:(y + 1) * w * 4]
        out += _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        out += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    else:
        raw = bytearray()
        for y in range(h):
            raw.append(0)
            raw += image.indices[y * w:(y + 1) * w]
        plte = b"".join(bytes(c) for c in image.palette)
        out += _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0))
        out += _chunk(b"PLTE", plte)
        if image.masking == MASK_TRANSPARENT_COLOR:
            # tRNS gives one alpha byte per palette entry, up to the last
            # non-opaque one.
            last = image.transparent_color
            trns = bytearray(b"\xFF" * (last + 1))
            trns[last] = 0
            out += _chunk(b"tRNS", bytes(trns))
        out += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))

    out += _chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(out)


def _c_array(name, data, per_line=16):
    lines = ["const unsigned char %s[%d] = {" % (name, len(data))]
    for i in range(0, len(data), per_line):
        lines.append("    " + "".join("0x%02X," % b for b in data[i:i + per_line]))
    lines.append("};")
    return "\n".join(lines)


def write_cpp(cpp_path, hpp_path, name, image, source_name, opaque=False):
    guard_include = hpp_path.rsplit("/", 1)[-1]

    # The Image struct itself is hand-written in src/frontend/moria_assets.hpp
    # so that several generated headers can be included together.
    hpp = """// Generated by tools/iff_convert.py from %s -- do not edit.
#pragma once

#include "moria_assets.hpp"

namespace moria::assets {

extern const Image %s;

}  // namespace moria::assets
""" % (source_name, name)

    alpha_note = ("alpha forced opaque, as putgfx() copies every bitplane"
                  if opaque else
                  "alpha as the ILBM declared it")

    cpp = """// Generated by tools/iff_convert.py from %s -- do not edit.
// %dx%d, %d bitplanes, %d palette entries, masking mode %d.
// Pixels are unmodified; %s.
#include "%s"

namespace moria::assets {
namespace {

%s

}  // namespace

const Image %s = {%d, %d, %s_pixels};

}  // namespace moria::assets
""" % (source_name, image.width, image.height, image.planes, len(image.palette),
       image.masking, alpha_note, guard_include,
       _c_array("%s_pixels" % name, image.rgba(opaque=opaque)), name,
       image.width, image.height, name)

    with open(hpp_path, "w") as fh:
        fh.write(hpp)
    with open(cpp_path, "w") as fh:
        fh.write(cpp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="source .iff (ILBM) file")
    ap.add_argument("--png", help="write a PNG here")
    ap.add_argument("--cpp", help="write an embeddable C++ source here")
    ap.add_argument("--hpp", help="write the matching C++ header here")
    ap.add_argument("--name", help="C++ identifier for the image")
    ap.add_argument("--opaque", action="store_true",
                    help="force alpha to 255 in the C++ output, reproducing "
                         "the Amiga's opaque bitplane blit")
    ap.add_argument("--info", action="store_true", help="print header details")
    args = ap.parse_args(argv)

    # A .cpp without its .hpp used to emit #include "" and defer the failure
    # to whoever compiled it. Both halves or neither.
    if bool(args.cpp) != bool(args.hpp):
        ap.error("--cpp and --hpp must be given together")
    if args.cpp and not args.name:
        ap.error("--cpp/--hpp require --name")
    if args.name and not C_IDENTIFIER.match(args.name):
        ap.error("--name %r is not a valid C++ identifier" % args.name)

    with open(args.input, "rb") as fh:
        image = parse_ilbm(fh.read())

    if args.info or not (args.png or args.cpp):
        print("%s: %dx%d, %d planes, %d colours, masking %d"
              % (args.input, image.width, image.height, image.planes,
                 len(image.palette), image.masking))
        if image.masking == MASK_TRANSPARENT_COLOR:
            print("transparent colour: %d" % image.transparent_color)
        print("palette: " + " ".join("#%02X%02X%02X" % c for c in image.palette))

    if args.png:
        write_png(args.png, image)
    if args.cpp:
        write_cpp(args.cpp, args.hpp, args.name, image,
                  args.input.rsplit("/", 1)[-1], opaque=args.opaque)
    return 0


if __name__ == "__main__":
    sys.exit(main())
