# This file is Copyright (c) 2019 Frank Buss <fb@frank-buss.de>
# License: BSD

import os

from migen import *

from litex.soc.interconnect import wishbone

# Terminal emulation with 640 x 480 pixels, 80 x 30 characters, individual foreground and background
# color per character (VGA palette) and user definable font, with code page 437 VGA font initialized.
# 60 Hz framerate, if vga_clk is 25.175 MHz. Independent system clock possible, internal dual-port
# block RAM.
#
# Memory layout:
# 0x0000 - 0x12bf = 2 bytes per character:
#    character: index in VGA font
#    color: low nibble is foreground color, and high nibble is background color, VGA palette
# 0x12c0 - 0x22bf = VGA font, 16 lines per character, 8 bits width
#
# VGA timings:
# clocks per line:
# 1. HSync low pulse for 96 clocks
# 2. back porch for 48 clocks
# 3. data for 640 clocks
# 4. front porch for 16 clocks
#
# VSync timing per picture (800 clocks = 1 line):
# 1. VSync low pulse for 2 lines
# 2. back porch for 29 lines
# 3. data for 480 lines
# 4. front porch for 10 lines

# Helpers ------------------------------------------------------------------------------------------

def get_path(filename):
    """Return filename relative to caller script, if available, otherwise relative to this package
       script"""
    if os.path.isfile(filename):
        return filename
    path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(path, filename)

def read_ram_init_file(filename, size):
    """Read file, if not empty, and test for size. If empty, init with 0"""
    if filename == '':
        return [0] * size
    else:
        with open(get_path(filename), "rb") as file:
            data = list(file.read())
        if len(data) != size:
            raise ValueError("Invalid size for file {}. Expected size: {}, actual size: {}".format(
                filename, size, len(data)))
        return data

# Terminal -----------------------------------------------------------------------------------------

class Terminal(Module):
    def __init__(self, pads=None, font_filename="cp437.bin", screen_init_filename="screen-init.bin"):
        # Wishbone interface
        self.bus = bus = wishbone.Interface(data_width=8)

        # Acknowledge immediately
        self.sync += [
            bus.ack.eq(0),
            If (bus.cyc & bus.stb & ~bus.ack, bus.ack.eq(1))
        ]

        # RAM initialization
        screen_init = read_ram_init_file(screen_init_filename, 4800)
        font = read_ram_init_file(font_filename, 4096)
        ram_init = screen_init + font

        # Create RAM
        mem = Memory(width=8, depth=8896, init=ram_init)
        self.specials += mem
        wrport = mem.get_port(write_capable=True, clock_domain="sys")
        self.specials += wrport
        rdport = mem.get_port(write_capable=False, clock_domain="vga")
        self.specials += rdport

        # Memory map internal block RAM to Wishbone interface
        self.sync += [        
            wrport.we.eq(0),
            If (bus.cyc & bus.stb & bus.we & ~bus.ack,
                wrport.we.eq(1),
                wrport.dat_w.eq(bus.dat_w),
            ),
        ]
        
        self.comb += [
            wrport.adr.eq(bus.adr),
            bus.dat_r.eq(wrport.dat_r)
        ]

        # Display resolution
        WIDTH  = 640
        HEIGHT = 480

        # Offset to font data in RAM
        FONT_ADDR = 80 * 30 * 2

        # VGA output
        self.red   = red   = Signal(8) if pads is None else pads.red
        self.green = green = Signal(8) if pads is None else pads.green
        self.blue  = blue  = Signal(8) if pads is None else pads.blue
        self.hsync = hsync = Signal()  if pads is None else pads.hsync
        self.vsync = vsync = Signal()  if pads is None else pads.vsync

        # VGA timings
        H_SYNC_PULSE  = 96
        H_BACK_PORCH  = 48 + H_SYNC_PULSE
        H_DATA        = WIDTH + H_BACK_PORCH
        H_FRONT_PORCH = 16 + H_DATA

        V_SYNC_PULSE  = 2
        V_BACK_PORCH  = 29 + V_SYNC_PULSE
        V_DATA        = HEIGHT + V_BACK_PORCH
        V_FRONT_PORCH = 10 + V_DATA

        pixel_counter = Signal(10)
        line_counter  = Signal(10)

        # Read address in text RAM
        text_addr = Signal(16)

        # Read address in text RAM at line start
        text_addr_start = Signal(16)

        # Current line within a character, 0 to 15
        fline = Signal(4)

        # Current x position within a character, 0 to 7
        fx = Signal(3)

        # Current and next byte for a character line
        fbyte     = Signal(8)
        next_byte = Signal(8)

        # Current foreground color
        fgcolor      = Signal(24)
        next_fgcolor = Signal(24)

        # Current background color
        bgcolor = Signal(24)

        # Current fg/bg color index from RAM
        color = Signal(8)

        # Color index and lookup
        color_index  = Signal(4)
        color_lookup = Signal(24)

        # VGA palette
        palette = [
            0x000000, 0x0000aa, 0x00aa00, 0x00aaaa, 0xaa0000, 0xaa00aa, 0xaa5500, 0xaaaaaa,
            0x555555, 0x5555ff, 0x55ff55, 0x55ffff, 0xff5555, 0xff55ff, 0xffff55, 0xffffff
        ]
        cases = {}
        for i in range(16):
            cases[i] = color_lookup.eq(palette[i])
        self.comb += Case(color_index, cases)

        self.sync.vga += [
            # Default values
            red.eq(0),
            green.eq(0),
            blue.eq(0),

            # Show pixels
            If((line_counter >= V_BACK_PORCH) & (line_counter < V_DATA),
                If((pixel_counter >= H_BACK_PORCH) & (pixel_counter < H_DATA),
                    If(fbyte[7],
                        red.eq(fgcolor[16:24]),
                        green.eq(fgcolor[8:16]),
                        blue.eq(fgcolor[0:8])
                    ).Else(
                        red.eq(bgcolor[16:24]),
                        green.eq(bgcolor[8:16]),
                        blue.eq(bgcolor[0:8])
                    ),
                    fbyte.eq(Cat(Signal(), fbyte[:-1]))
                )
            ),

            # Load next character code, font line and color
            If(fx == 1,
                # schedule reading the character code
                rdport.adr.eq(text_addr),
                text_addr.eq(text_addr + 1)
            ),
            If(fx == 2,
                # Schedule reading the color
                rdport.adr.eq(text_addr),
                text_addr.eq(text_addr + 1)
            ),
            If(fx == 3,
                # Read character code, and set address for font line
                rdport.adr.eq(FONT_ADDR + Cat(Signal(4), rdport.dat_r) + fline)
            ),
            If(fx == 4,
                # Read color
                color.eq(rdport.dat_r)
            ),
            If(fx == 5,
                # Read font line, and set color index to get foreground color
                next_byte.eq(rdport.dat_r),
                color_index.eq(color[0:4]),
            ),
            If(fx == 6,
                # Get next foreground color, and set color index for background color
                next_fgcolor.eq(color_lookup),
                color_index.eq(color[4:8])
            ),
            If(fx == 7,
                # Set background color and everything for the next 8 pixels
                bgcolor.eq(color_lookup),
                fgcolor.eq(next_fgcolor),
                fbyte.eq(next_byte)
            ),
            fx.eq(fx + 1),
            If(fx == 7, fx.eq(0)),

            # Horizontal timing for one line
            pixel_counter.eq(pixel_counter + 1),
            If(pixel_counter < H_SYNC_PULSE,
                hsync.eq(0)
            ).Elif (pixel_counter < H_BACK_PORCH,
                hsync.eq(1)
            ),
            If(pixel_counter == H_BACK_PORCH - 9,
                # Prepare reading first character of next line
                fx.eq(0),
                text_addr.eq(text_addr_start)
            ),
            If(pixel_counter == H_FRONT_PORCH,
                # Initilize next line
                pixel_counter.eq(0),
                line_counter.eq(line_counter + 1),

                # Font height is 16 pixels
                fline.eq(fline + 1),
                If(fline == 15,
                    fline.eq(0),
                    text_addr_start.eq(text_addr_start + 2 * 80)
                )
            ),

            # Vertical timing for one screen
            If(line_counter < V_SYNC_PULSE,
                vsync.eq(0)
            ).Elif(line_counter < V_BACK_PORCH,
                vsync.eq(1)
            ),
            If(line_counter == V_FRONT_PORCH,
                # End of image
                line_counter.eq(0)
            ),
            If(line_counter == V_BACK_PORCH - 1,
                # Prepare generating next image data
                fline.eq(0),
                text_addr_start.eq(0)
            )
        ]
