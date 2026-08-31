#!/usr/bin/env python3
"""Tests for tools/gen_font.py.

A font generator that quietly crops, pads or misaligns glyphs produces a
header that compiles and renders unreadable text. Every rejection case here
exists because the failure would otherwise be silent.
"""

import os
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, TOOLS)

import gen_font  # noqa: E402

GENERATOR = os.path.join(TOOLS, "gen_font.py")


def psf1(charsize, count=256, glyph_byte=0xA5, truncate=0):
    mode = 0x00 if count == 256 else 0x01
    header = gen_font.PSF1_MAGIC + bytes([mode, charsize])
    payload = bytearray()
    for code in range(count):
        payload += bytes([(glyph_byte + code) & 0xFF]) * charsize
    if truncate:
        payload = payload[:-truncate]
    return bytes(header + payload)


def psf2(width, height, count=256, glyph_byte=0x5A, truncate=0):
    charsize = height * ((width + 7) // 8)
    header = gen_font.PSF2_MAGIC + struct.pack(
        "<IIIIIII", 0, gen_font.PSF2_HEADER_SIZE, 0, count, charsize, height, width)
    payload = bytearray()
    for code in range(count):
        payload += bytes([(glyph_byte + code) & 0xFF]) * charsize
    if truncate:
        payload = payload[:-truncate]
    return bytes(header + payload)


class ReadFontTest(unittest.TestCase):
    def write(self, data, name="font.psf"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_psf1_8x8(self):
        count, width, height, stride, payload = gen_font.read_font(
            self.write(psf1(8)))
        self.assertEqual((count, width, height, stride), (256, 8, 8, 8))
        self.assertEqual(payload[:8], bytes([0xA5]) * 8)

    def test_psf2_8x8(self):
        count, width, height, stride, payload = gen_font.read_font(
            self.write(psf2(8, 8)))
        self.assertEqual((count, width, height, stride), (256, 8, 8, 8))
        self.assertEqual(payload[:8], bytes([0x5A]) * 8)

    def test_stride_comes_from_the_header_not_the_file_length(self):
        # One byte short. Deriving the stride from len(payload) // count would
        # give 7 and misalign every glyph after the first.
        with self.assertRaises(gen_font.FontError) as err:
            gen_font.read_font(self.write(psf1(8, truncate=1)))
        self.assertIn("truncated", str(err.exception))

    def test_truncated_psf2_is_refused(self):
        with self.assertRaises(gen_font.FontError):
            gen_font.read_font(self.write(psf2(8, 8, truncate=1)))

    def test_psf2_with_inconsistent_charsize_is_refused(self):
        broken = bytearray(psf2(8, 8))
        # charsize sits at byte 20: magic, version, headersize, flags, length.
        broken[20:24] = struct.pack("<I", 9)  # 8x8 needs 8 bytes per glyph
        with self.assertRaises(gen_font.FontError):
            gen_font.read_font(self.write(bytes(broken)))

    def test_not_a_font(self):
        with self.assertRaises(gen_font.FontError):
            gen_font.read_font(self.write(b"not a font at all"))


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.hpp = os.path.join(self.tmp.name, "font.generated.hpp")

    def write(self, data, name="font.psf"):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def run_tool(self, font_path):
        return subprocess.run(
            [sys.executable, GENERATOR, font_path, "--hpp", self.hpp],
            capture_output=True, text=True)

    def test_valid_8x8_reproduces_known_rows(self):
        result = self.run_tool(self.write(psf1(8)))
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(self.hpp) as fh:
            header = fh.read()
        # Glyph 0 is 0xA5 on every scanline, glyph 1 is 0xA6.
        self.assertIn("{0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5},", header)
        self.assertIn("{0xA6, 0xA6, 0xA6, 0xA6, 0xA6, 0xA6, 0xA6, 0xA6},", header)

    def test_8x16_is_refused_not_cropped(self):
        result = self.run_tool(self.write(psf1(16)))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("8x16", result.stderr)
        self.assertFalse(os.path.exists(self.hpp),
                         "a rejected font must not leave a header behind")

    def test_8x16_psf2_is_refused(self):
        result = self.run_tool(self.write(psf2(8, 16)))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(self.hpp))

    def test_truncated_is_refused(self):
        result = self.run_tool(self.write(psf1(8, truncate=1)))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("truncated", result.stderr)
        self.assertFalse(os.path.exists(self.hpp))


if __name__ == "__main__":
    unittest.main()
