#!/usr/bin/env python3
"""Tests for tools/iff_convert.py.

The artwork in the 1.2 distribution is not plain opaque ILBM: both tile
atlases declare masking mode 2 with transparentColor 0. These fixtures pin
down that transparency survives conversion, in both output formats.
"""

import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, TOOLS)

import iff_convert  # noqa: E402

CONVERTER = os.path.join(TOOLS, "iff_convert.py")


def make_ilbm(width, height, planes, masking, transparent_color, plane_rows,
              palette):
    """Build an uncompressed ILBM.

    `plane_rows` is [row][plane] -> bytes, already padded to the ILBM row
    width, with the mask plane last when masking mode 1 is in use.
    """
    bmhd = struct.pack(">HHhhBBBBHBBhh", width, height, 0, 0, planes, masking,
                       0, 0, transparent_color, 5, 11, width, height)
    cmap = b"".join(bytes(c) for c in palette)
    body = b"".join(b"".join(row) for row in plane_rows)

    def chunk(tag, payload):
        pad = b"\x00" if (len(payload) & 1) else b""
        return tag + struct.pack(">I", len(payload)) + payload + pad

    chunks = chunk(b"BMHD", bmhd) + chunk(b"CMAP", cmap) + chunk(b"BODY", body)
    return b"FORM" + struct.pack(">I", 4 + len(chunks)) + b"ILBM" + chunks


def read_png(path):
    """Minimal reader for the PNGs this tool writes (filter type 0 only)."""
    with open(path, "rb") as fh:
        data = fh.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos = 8
    chunks = {}
    order = []
    idat = b""
    while pos < len(data):
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + size]
        order.append(tag)
        if tag == b"IDAT":
            idat += payload
        else:
            chunks[tag] = payload
        pos += 12 + size

    w, h, depth, colour = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    raw = zlib.decompress(idat)
    channels = {3: 1, 6: 4}[colour]
    stride = w * channels
    rows = []
    for y in range(h):
        start = y * (stride + 1)
        assert raw[start] == 0, "unexpected PNG filter type"
        rows.append(raw[start + 1:start + 1 + stride])
    return {"width": w, "height": h, "depth": depth, "colour_type": colour,
            "rows": rows, "chunks": chunks, "order": order}


class MaskPlaneTest(unittest.TestCase):
    """Masking mode 1: an explicit mask plane, one bit per pixel."""

    def setUp(self):
        # 2x1, one bitplane. Colour indices [0, 1]; mask says pixel 0 opaque,
        # pixel 1 transparent.
        colour_plane = bytes([0x40, 0x00])  # bit set at x=1 -> index 1
        mask_plane = bytes([0x80, 0x00])    # bit set at x=0 -> opaque
        self.iff = make_ilbm(2, 1, 1, iff_convert.MASK_PLANE, 0,
                             [[colour_plane, mask_plane]],
                             [(0x11, 0x22, 0x33), (0xAA, 0xBB, 0xCC)])

    def test_indices_and_alpha(self):
        image = iff_convert.parse_ilbm(self.iff)
        self.assertEqual(list(image.indices), [0, 1])
        self.assertEqual(list(image.alpha), [255, 0])

    def test_rgba_carries_the_mask(self):
        image = iff_convert.parse_ilbm(self.iff)
        rgba = image.rgba()
        self.assertEqual(list(rgba), [0x11, 0x22, 0x33, 255,
                                      0xAA, 0xBB, 0xCC, 0])

    def test_opaque_flag_overrides_it(self):
        image = iff_convert.parse_ilbm(self.iff)
        self.assertEqual(list(image.rgba(opaque=True)[3::4]), [255, 255])

    def test_png_is_rgba(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = os.path.join(tmp, "out.png")
            iff_convert.write_png(png, iff_convert.parse_ilbm(self.iff))
            decoded = read_png(png)
        self.assertEqual(decoded["colour_type"], 6, "mask plane needs RGBA")
        self.assertEqual(list(decoded["rows"][0]),
                         [0x11, 0x22, 0x33, 255, 0xAA, 0xBB, 0xCC, 0])


class TransparentColourTest(unittest.TestCase):
    """Masking mode 2, as both shipped tile atlases actually use."""

    def setUp(self):
        colour_plane = bytes([0x40, 0x00])  # indices [0, 1]
        self.iff = make_ilbm(2, 1, 1, iff_convert.MASK_TRANSPARENT_COLOR, 0,
                             [[colour_plane]],
                             [(0x11, 0x22, 0x33), (0xAA, 0xBB, 0xCC)])

    def test_transparent_colour_becomes_alpha_zero(self):
        image = iff_convert.parse_ilbm(self.iff)
        self.assertEqual(list(image.indices), [0, 1])
        self.assertEqual(list(image.alpha), [0, 255])
        self.assertEqual(list(image.rgba()[3::4]), [0, 255])

    def test_opaque_flag_overrides_it(self):
        image = iff_convert.parse_ilbm(self.iff)
        self.assertEqual(list(image.rgba(opaque=True)[3::4]), [255, 255])

    def test_png_is_indexed_with_trns(self):
        with tempfile.TemporaryDirectory() as tmp:
            png = os.path.join(tmp, "out.png")
            iff_convert.write_png(png, iff_convert.parse_ilbm(self.iff))
            decoded = read_png(png)
        self.assertEqual(decoded["colour_type"], 3, "should stay indexed")
        self.assertIn(b"tRNS", decoded["chunks"])
        self.assertEqual(decoded["chunks"][b"tRNS"][0], 0,
                         "palette entry 0 must be transparent")
        self.assertEqual(list(decoded["rows"][0]), [0, 1])


class UnmaskedTest(unittest.TestCase):
    """The title screen is masking mode 0 and must be unaffected."""

    def test_fully_opaque(self):
        colour_plane = bytes([0x40, 0x00])
        iff = make_ilbm(2, 1, 1, iff_convert.MASK_NONE, 0, [[colour_plane]],
                        [(0x11, 0x22, 0x33), (0xAA, 0xBB, 0xCC)])
        image = iff_convert.parse_ilbm(iff)
        self.assertEqual(list(image.alpha), [255, 255])
        self.assertFalse(image.has_transparency)

    def test_lasso_masking_is_refused(self):
        colour_plane = bytes([0x40, 0x00])
        iff = make_ilbm(2, 1, 1, iff_convert.MASK_LASSO, 0, [[colour_plane]],
                        [(0, 0, 0), (1, 1, 1)])
        with self.assertRaises(iff_convert.IffError):
            iff_convert.parse_ilbm(iff)

    def test_truncated_body_is_refused(self):
        iff = make_ilbm(2, 1, 1, iff_convert.MASK_NONE, 0, [[b"\x40"]],
                        [(0, 0, 0), (1, 1, 1)])
        with self.assertRaises(iff_convert.IffError):
            iff_convert.parse_ilbm(iff)


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.iff = os.path.join(self.tmp.name, "fixture.iff")
        with open(self.iff, "wb") as fh:
            fh.write(make_ilbm(2, 1, 1, iff_convert.MASK_NONE, 0,
                               [[bytes([0x40, 0x00])]],
                               [(0, 0, 0), (255, 255, 255)]))

    def run_tool(self, *args):
        return subprocess.run([sys.executable, CONVERTER, self.iff, *args],
                              capture_output=True, text=True)

    def test_cpp_without_hpp_is_refused(self):
        out = os.path.join(self.tmp.name, "out.cpp")
        result = self.run_tool("--cpp", out, "--name", "image")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--cpp and --hpp must be given together", result.stderr)
        self.assertFalse(os.path.exists(out),
                         "no half-written source should be left behind")

    def test_invalid_name_is_refused(self):
        result = self.run_tool("--cpp", os.path.join(self.tmp.name, "o.cpp"),
                               "--hpp", os.path.join(self.tmp.name, "o.hpp"),
                               "--name", "9-invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a valid C++ identifier", result.stderr)

    def test_paired_output_writes_a_usable_include(self):
        cpp = os.path.join(self.tmp.name, "out.cpp")
        hpp = os.path.join(self.tmp.name, "out.hpp")
        result = self.run_tool("--cpp", cpp, "--hpp", hpp, "--name", "image")
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(cpp) as fh:
            source = fh.read()
        self.assertIn('#include "out.hpp"', source)
        self.assertNotIn('#include ""', source)


if __name__ == "__main__":
    unittest.main()
