# FPC-III HDMI support

This is an implementation of simple HDMI video output generation for the
FPC-III/ECP5 hardware.  It is made from two components: the `fpc_hdmi`
module provides a dual port 24-bit wide RGB scan line buffer and
repeatedly scans it to generate TMDS output; and the `chargen` modules
provides a Wishbone interface to a VGA-ish text mode screen memory
buffer, from which it populates the `fpc_hdmi` scan line buffer.

The `chargen` module expects a 128 character 16x32 monospaced antialiased
bitmap font, read from `font.hex`; the supplied `font.c` demonstrates how
to generate the bitmaps using FreeType 2.

By default, the display resolution is 1600x900, providing a 100x28 character
grid using 16x32 fonts.
