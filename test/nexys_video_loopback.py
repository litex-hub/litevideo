#!/usr/bin/env python3
import argparse
import os

from litex.gen import *
from litex.gen.genlib.resetsync import AsyncResetSynchronizer
from litex.gen.fhdl.specials import Tristate
from litex.gen.genlib.misc import WaitTimer, BitSlip
from litex.build.xilinx import VivadoProgrammer

from litex.boards.platforms import nexys_video

from litex.soc.integration.builder import *

from litevideo.input.edid import EDID
from litevideo.input.decoding import Decoding

from litevideo.output.hdmi.s7 import S7HDMIOutPHY, S7HDMIOutEncoderSerializer


class _CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_clk200 = ClockDomain()

        clk100 = platform.request("clk100")
        rst = platform.request("cpu_reset")

        pll_locked = Signal()
        pll_fb = Signal()
        pll_sys = Signal()
        pll_clk200 = Signal()
        self.specials += [
            Instance("PLLE2_BASE",
                p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                # VCO @ 800 MHz
                p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=10.0,
                p_CLKFBOUT_MULT=8, p_DIVCLK_DIVIDE=1,
                i_CLKIN1=clk100, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

                # 100 MHz
                p_CLKOUT0_DIVIDE=8, p_CLKOUT0_PHASE=0.0,
                o_CLKOUT0=pll_sys,

                # 200 MHz
                p_CLKOUT3_DIVIDE=4, p_CLKOUT3_PHASE=0.0,
                o_CLKOUT3=pll_clk200
            ),
            Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
            Instance("BUFG", i_I=pll_clk200, o_O=self.cd_clk200.clk),
            AsyncResetSynchronizer(self.cd_sys, ~pll_locked | ~rst),
            AsyncResetSynchronizer(self.cd_clk200, ~pll_locked | rst),
        ]

        reset_counter = Signal(4, reset=15)
        ic_reset = Signal(reset=1)
        self.sync.clk200 += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL", i_REFCLK=ClockSignal("clk200"), i_RST=ic_reset)


# TODO: to be removed when we'll have the phase detector working
class InvalidSymbolDetector(Module):
    def __init__(self, symbol):
        self.invalid = Signal()

        # # #

        valid_symbols = [
            0b1111111111, 0b0100000000, 0b0111111111, 0b1100000000,
            0b0111111110, 0b1100000001, 0b1111111110, 0b0100000001,
            0b0111111100, 0b1100000011, 0b1111111100, 0b0100000011,
            0b1111111101, 0b0100000010, 0b0111111101, 0b1100000010,
            0b0111111000, 0b1100000111, 0b1111111000, 0b0100000111,
            0b1111111001, 0b0100000110, 0b0111111001, 0b1100000110,
            0b1111111011, 0b0100000100, 0b0111111011, 0b1100000100,
            0b0111111010, 0b1100000101, 0b1111111010, 0b0100000101,
            0b0111110000, 0b0100001111, 0b1111110001, 0b0100001110,
            0b0111110001, 0b1100001110, 0b1111110011, 0b0100001100,
            0b0111110011, 0b1100001100, 0b0111110010, 0b1100001101,
            0b1111110010, 0b0100001101, 0b1111110111, 0b0100001000,
            0b0111110111, 0b1100001000, 0b0111110110, 0b1100001001,
            0b1111110110, 0b0100001001, 0b0111110100, 0b1100001011,
            0b1111110100, 0b0100001011, 0b1001011111, 0b0010100000,
            0b0001011111, 0b1010100000, 0b1100011111, 0b0111100000,
            0b0100011111, 0b1111100000, 0b0100011110, 0b0111100001,
            0b1111100011, 0b0100011100, 0b0111100011, 0b1100011100,
            0b0111100010, 0b0100011101, 0b1111100111, 0b0100011000,
            0b0111100111, 0b1100011000, 0b0111100110, 0b1100011001,
            0b1111100110, 0b0100011001, 0b0111100100, 0b0100011011,
            0b1001001111, 0b0010110000, 0b0001001111, 0b1010110000,
            0b1111101111, 0b0100010000, 0b0111101111, 0b1100010000,
            0b0111101110, 0b1100010001, 0b1111101110, 0b0100010001,
            0b0111101100, 0b1100010011, 0b1111101100, 0b0100010011,
            0b1001000111, 0b1010111000, 0b0111101000, 0b0100010111,
            0b0010111100, 0b1001000011, 0b1010111100, 0b0001000011,
            0b0010111110, 0b1001000001, 0b1010111110, 0b0001000001,
            0b1010111111, 0b0001000000, 0b0010111111, 0b1001000000,
            0b1100111111, 0b0111000000, 0b0100111111, 0b1111000000,
            0b0100111110, 0b1111000001, 0b1100111110, 0b0111000001,
            0b0100111100, 0b0111000011, 0b1100111101, 0b0111000010,
            0b0100111101, 0b1111000010, 0b1111000111, 0b0100111000,
            0b0111000111, 0b1100111000, 0b0111000110, 0b0100111001,
            0b1100111011, 0b0111000100, 0b0100111011, 0b1111000100,
            0b1001101111, 0b0010010000, 0b0001101111, 0b1010010000,
            0b1111001111, 0b0100110000, 0b0111001111, 0b1100110000,
            0b0111001110, 0b1100110001, 0b1111001110, 0b0100110001,
            0b0111001100, 0b0100110011, 0b1001100111, 0b0010011000,
            0b0001100111, 0b1010011000, 0b1100110111, 0b0111001000,
            0b0100110111, 0b1111001000, 0b1001100011, 0b1010011100,
            0b0010011110, 0b1001100001, 0b1010011110, 0b0001100001,
            0b1010011111, 0b0001100000, 0b0010011111, 0b1001100000,
            0b1111011111, 0b0100100000, 0b0111011111, 0b1100100000,
            0b0111011110, 0b1100100001, 0b1111011110, 0b0100100001,
            0b0111011100, 0b1100100011, 0b1111011100, 0b0100100011,
            0b1001110111, 0b0010001000, 0b0001110111, 0b1010001000,
            0b0111011000, 0b0100100111, 0b1001110011, 0b0010001100,
            0b0001110011, 0b1010001100, 0b1001110001, 0b1010001110,
            0b1010001111, 0b0001110000, 0b0010001111, 0b1001110000,
            0b1100101111, 0b0111010000, 0b0100101111, 0b1111010000,
            0b1001111011, 0b0010000100, 0b0001111011, 0b1010000100,
            0b1001111001, 0b0010000110, 0b0001111001, 0b1010000110,
            0b1010000111, 0b1001111000, 0b1001111101, 0b0010000010,
            0b0001111101, 0b1010000010, 0b0001111100, 0b1010000011,
            0b1001111100, 0b0010000011, 0b0001111110, 0b1010000001,
            0b1001111110, 0b0010000001, 0b1001111111, 0b0010000000,
            0b0001111111, 0b1010000000, 0b1101111111, 0b0110000000,
            0b0101111111, 0b1110000000, 0b0101111110, 0b1110000001,
            0b1101111110, 0b0110000001, 0b0101111100, 0b1110000011,
            0b1101111100, 0b0110000011, 0b1101111101, 0b0110000010,
            0b0101111101, 0b1110000010, 0b0101111000, 0b0110000111,
            0b1101111001, 0b0110000110, 0b0101111001, 0b1110000110,
            0b1101111011, 0b0110000100, 0b0101111011, 0b1110000100,
            0b1000101111, 0b0011010000, 0b0000101111, 0b1011010000,
            0b1110001111, 0b0101110000, 0b0110001111, 0b1101110000,
            0b0110001110, 0b0101110001, 0b1101110011, 0b0110001100,
            0b0101110011, 0b1110001100, 0b1000100111, 0b1011011000,
            0b1101110111, 0b0110001000, 0b0101110111, 0b1110001000,
            0b0011011100, 0b1000100011, 0b1011011100, 0b0000100011,
            0b0011011110, 0b1000100001, 0b1011011110, 0b0000100001,
            0b1011011111, 0b0000100000, 0b0011011111, 0b1000100000,
            0b1110011111, 0b0101100000, 0b0110011111, 0b1101100000,
            0b0110011110, 0b1101100001, 0b1110011110, 0b0101100001,
            0b0110011100, 0b0101100011, 0b1000110111, 0b0011001000,
            0b0000110111, 0b1011001000, 0b1101100111, 0b0110011000,
            0b0101100111, 0b1110011000, 0b1000110011, 0b1011001100,
            0b0011001110, 0b1000110001, 0b1011001110, 0b0000110001,
            0b1011001111, 0b0000110000, 0b0011001111, 0b1000110000,
            0b1101101111, 0b0110010000, 0b0101101111, 0b1110010000,
            0b1000111011, 0b0011000100, 0b0000111011, 0b1011000100,
            0b1000111001, 0b1011000110, 0b1011000111, 0b0000111000,
            0b0011000111, 0b1000111000, 0b1000111101, 0b0011000010,
            0b0000111101, 0b1011000010, 0b1011000011, 0b1000111100,
            0b0000111110, 0b1011000001, 0b1000111110, 0b0011000001,
            0b1000111111, 0b0011000000, 0b0000111111, 0b1011000000,
            0b1110111111, 0b0101000000, 0b0110111111, 0b1101000000,
            0b0110111110, 0b1101000001, 0b1110111110, 0b0101000001,
            0b0110111100, 0b1101000011, 0b1110111100, 0b0101000011,
            0b1000010111, 0b1011101000, 0b0110111000, 0b0101000111,
            0b0011101100, 0b1000010011, 0b1011101100, 0b0000010011,
            0b0011101110, 0b1000010001, 0b1011101110, 0b0000010001,
            0b1011101111, 0b0000010000, 0b0011101111, 0b1000010000,
            0b1101001111, 0b0110110000, 0b0101001111, 0b1110110000,
            0b1000011011, 0b1011100100, 0b0011100110, 0b1000011001,
            0b1011100110, 0b0000011001, 0b1011100111, 0b0000011000,
            0b0011100111, 0b1000011000, 0b1000011101, 0b1011100010,
            0b1011100011, 0b0000011100, 0b0011100011, 0b1000011100,
            0b1011100001, 0b1000011110, 0b1000011111, 0b0011100000,
            0b0000011111, 0b1011100000, 0b1101011111, 0b0110100000,
            0b0101011111, 0b1110100000, 0b0011110100, 0b1000001011,
            0b1011110100, 0b0000001011, 0b0011110110, 0b1000001001,
            0b1011110110, 0b0000001001, 0b1011110111, 0b0000001000,
            0b0011110111, 0b1000001000, 0b0011110010, 0b1000001101,
            0b1011110010, 0b0000001101, 0b1011110011, 0b0000001100,
            0b0011110011, 0b1000001100, 0b1011110001, 0b0000001110,
            0b0011110001, 0b1000001110, 0b1000001111, 0b1011110000,
            0b0011111010, 0b1000000101, 0b1011111010, 0b0000000101,
            0b1011111011, 0b0000000100, 0b0011111011, 0b1000000100,
            0b1011111001, 0b0000000110, 0b0011111001, 0b1000000110,
            0b0011111000, 0b1000000111, 0b1011111000, 0b0000000111,
            0b1011111101, 0b0000000010, 0b0011111101, 0b1000000010,
            0b0011111100, 0b1000000011, 0b1011111100, 0b0000000011,
            0b0011111110, 0b1000000001, 0b1011111110, 0b0000000001,
            0b1011111111, 0b0000000000, 0b0011111111, 0b1000000000,
            0b0010101011, 0b0101010100, 0b1010101011, 0b1101010100]

        self.comb += self.invalid.eq(1)
        for s in valid_symbols:
            self.comb += If(symbol == s, self.invalid.eq(0))


class AlignmentDetector(Module):
    def __init__(self, invalid_symbol):
        self.delay_value = Signal(5)
        self.delay_ce = Signal()
        self.bitslip_value = Signal(4)

        # # #

        count = Signal(20)
        signal_quality = Signal(28)
        holdoff = Signal(10)
        error_seen = Signal()

        self.sync.pix += [
            error_seen.eq(0),
            If(holdoff == 0,
                If(invalid_symbol,
                    error_seen.eq(1)
                )
            ).Else(
                holdoff.eq(holdoff-1)
            ),
            self.delay_ce.eq(0),
            If(error_seen,
                If(signal_quality[24:28] == 0xf,
                    holdoff.eq(2**10-1),
                    If(self.delay_value == 31,
                        self.bitslip_value.eq(self.bitslip_value+1)
                    ),
                    self.delay_value.eq(self.delay_value+1),
                    self.delay_ce.eq(1),
                    signal_quality[24:28].eq(0x4)
                ).Else(
                    signal_quality.eq(signal_quality + 0x100000)
                )
            ).Else(
                If(signal_quality[24:28] != 0,
                    signal_quality.eq(signal_quality-1)
                )
            )
        ]


class Deserialiser1to10(Module):
    def __init__(self):
        self.delay_ce = Signal()
        self.delay_value = Signal(5)
        self.bitslip_value = Signal(4)

        self.serial = Signal()
        self.reset = Signal()
        self.data = Signal(10)

        # # #

        delayed = Signal()
        shift = Signal(2)

        self.submodules.bitslip = ClockDomainsRenamer("pix")(BitSlip(10))
        self.comb += self.bitslip.value.eq(self.bitslip_value)

        self.specials += [
            Instance("IDELAYE2",
                p_DELAY_SRC="DATAIN", p_SIGNAL_PATTERN="DATA",
                p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=200.0,
                p_PIPE_SEL="FALSE", p_IDELAY_TYPE="VAR_LOAD", p_IDELAY_VALUE=0,

                i_C=ClockSignal("pix"),
                i_LD=1,
                i_CE=self.delay_ce,
                i_LDPIPEEN=0, i_INC=0,
                i_CINVCTRL=0, i_CNTVALUEIN=self.delay_value,

                i_DATAIN=self.serial, o_DATAOUT=delayed
            ),
            Instance("ISERDESE2",
                p_DATA_WIDTH=10, p_DATA_RATE="DDR",
                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="IFD",

                i_DDLY=delayed,
                i_CE1=1, i_CE2=1,
                i_RST=self.reset,
                i_CLK=ClockSignal("pix5x"), i_CLKB=~ClockSignal("pix5x"), i_CLKDIV=ClockSignal("pix"),
                i_BITSLIP=0,

                o_Q1=self.bitslip.i[9], o_Q2=self.bitslip.i[8],
                o_Q3=self.bitslip.i[7], o_Q4=self.bitslip.i[6],
                o_Q5=self.bitslip.i[5], o_Q6=self.bitslip.i[4],
                o_Q7=self.bitslip.i[3], o_Q8=self.bitslip.i[2],

                o_SHIFTOUT1=shift[0], o_SHIFTOUT2=shift[1],
            ),
            Instance("ISERDESE2",
                p_DATA_WIDTH=10, p_DATA_RATE="DDR",
                p_SERDES_MODE="SLAVE", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="IFD",

                i_DDLY=0,
                i_CE1=1, i_CE2=1,
                i_RST=self.reset,
                i_CLK=ClockSignal("pix5x"), i_CLKB=~ClockSignal("pix5x"), i_CLKDIV=ClockSignal("pix"),
                i_BITSLIP=0,

                o_SHIFTIN1=shift[0], o_SHIFTIN2=shift[1],

                #o_Q1=, o_Q2=,
                o_Q3=self.bitslip.i[1], o_Q4=self.bitslip.i[0],
                #o_Q5=, o_Q6=,
                #o_Q7=, o_Q8=
            ),
        ]
        self.comb += self.data.eq(self.bitslip.o)


class HDMIInputChannel(Module):
    def __init__(self, data):
        self.reset = Signal()

        self.ctl_valid = Signal()
        self.ctl = Signal(2)

        self.data_valid = Signal()
        self.data = Signal(8)

        # # #

        delay_ce = Signal()
        delay_value = Signal(5)
        bitslip = Signal()

        symbol = Signal(10)

        invalid_symbol_detector = InvalidSymbolDetector(symbol)
        self.submodules += invalid_symbol_detector

        alignment_detector = AlignmentDetector(invalid_symbol_detector.invalid)
        self.submodules += alignment_detector

        deserialiser = Deserialiser1to10()
        self.submodules += deserialiser
        self.comb += [
            deserialiser.delay_ce.eq(alignment_detector.delay_ce),
            deserialiser.delay_value.eq(alignment_detector.delay_value),
            deserialiser.bitslip_value.eq(alignment_detector.bitslip_value),
            deserialiser.reset.eq(self.reset),
            deserialiser.serial.eq(data),
            symbol.eq(deserialiser.data)
        ]

        decoder = Decoding()
        self.submodules += decoder
        self.comb += [
            decoder.valid_i.eq(1),
            decoder.input.eq(symbol),

            If(decoder.valid_o,
                If(decoder.output.de,
                    self.data_valid.eq(1),
                    self.data.eq(decoder.output.d)
                ).Else(
                    self.ctl_valid.eq(1),
                    self.ctl.eq(decoder.output.c)
                )
            )
        ]

class HDMILoopback(Module):
    def __init__(self, platform):
        self.submodules.crg = _CRG(platform)

        hdmi_in_pads = platform.request("hdmi_in")
        hdmi_out_pads = platform.request("hdmi_out")

        # input buffers
        hdmi_in_clk = Signal()
        hdmi_in_data = Signal(3)

        self.specials += [
            Instance("IBUFDS",
                i_I=hdmi_in_pads.clk_p,
                i_IB=hdmi_in_pads.clk_n,
                o_O=hdmi_in_clk),
            Instance("IBUFDS",
                i_I=hdmi_in_pads.data0_p,
                i_IB=hdmi_in_pads.data0_n,
                o_O=hdmi_in_data[0]),
            Instance("IBUFDS",
                i_I=hdmi_in_pads.data1_p,
                i_IB=hdmi_in_pads.data1_n,
                o_O=hdmi_in_data[1]),
            Instance("IBUFDS",
                i_I=hdmi_in_pads.data2_p,
                i_IB=hdmi_in_pads.data2_n,
                o_O=hdmi_in_data[2]),
        ]

        # edid
        edid_rom = [
            0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x00,
            0x04, 0x43, 0x07, 0xf2, 0x01, 0x00, 0x00, 0x00,
            0xff, 0x11, 0x01, 0x04, 0xa2, 0x4f, 0x00, 0x78,
            0x3e, 0xee, 0x91, 0xa3, 0x54, 0x4c, 0x99, 0x26,
            0x0f, 0x50, 0x54, 0x20, 0x00, 0x00, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x02, 0x3a,
            0x80, 0x18, 0x71, 0x38, 0x2d, 0x40, 0x58, 0x2c,
            0x04, 0x05, 0x0f, 0x48, 0x42, 0x00, 0x00, 0x1e,
            0x01, 0x1d, 0x80, 0x18, 0x71, 0x1c, 0x16, 0x20,
            0x58, 0x2c, 0x25, 0x00, 0x0f, 0x48, 0x42, 0x00,
            0x00, 0x9e, 0x01, 0x1d, 0x00, 0x72, 0x51, 0xd0,
            0x1e, 0x20, 0x6e, 0x28, 0x55, 0x00, 0x0f, 0x48,
            0x42, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0xfc,
            0x00, 0x48, 0x61, 0x6d, 0x73, 0x74, 0x65, 0x72,
            0x6b, 0x73, 0x0a, 0x20, 0x20, 0x20, 0x01, 0x74,
            0x02, 0x03, 0x18, 0x72, 0x47, 0x90, 0x85, 0x04,
            0x03, 0x02, 0x07, 0x06, 0x23, 0x09, 0x07, 0x07,
            0x83, 0x01, 0x00, 0x00, 0x65, 0x03, 0x0c, 0x00,
            0x10, 0x00, 0x8e, 0x0a, 0xd0, 0x8a, 0x20, 0xe0,
            0x2d, 0x10, 0x10, 0x3e, 0x96, 0x00, 0x1f, 0x09,
            0x00, 0x00, 0x00, 0x18, 0x8e, 0x0a, 0xd0, 0x8a,
            0x20, 0xe0, 0x2d, 0x10, 0x10, 0x3e, 0x96, 0x00,
            0x04, 0x03, 0x00, 0x00, 0x00, 0x18, 0x8e, 0x0a,
            0xa0, 0x14, 0x51, 0xf0, 0x16, 0x00, 0x26, 0x7c,
            0x43, 0x00, 0x1f, 0x09, 0x00, 0x00, 0x00, 0x98,
            0x8e, 0x0a, 0xa0, 0x14, 0x51, 0xf0, 0x16, 0x00,
            0x26, 0x7c, 0x43, 0x00, 0x04, 0x03, 0x00, 0x00,
            0x00, 0x98, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xc9,
        ]
        self.submodules.edid = EDID(hdmi_in_pads, edid_rom)
        self.comb += [
            hdmi_in_pads.hpa.eq(1),
            hdmi_in_pads.txen.eq(1)
        ]

        # mmcm
        pix_clk_pll = Signal()
        pix5x_clk_pll = Signal()
        pix_clk = Signal()
        pix5x_clk = Signal()
        mmcm_fb = Signal()
        mmcm_locked = Signal()
        self.specials += [
            Instance("MMCME2_ADV",
                p_BANDWIDTH="OPTIMIZED", i_RST=0, o_LOCKED=mmcm_locked,

                # VCO
                p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=6.7,
                p_CLKFBOUT_MULT_F=5.0, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=1,
                i_CLKIN1=hdmi_in_clk, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,

                # pix clk
                p_CLKOUT0_DIVIDE_F=5.0, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=pix_clk_pll,
                # pix5x clk
                p_CLKOUT1_DIVIDE=1, p_CLKOUT1_PHASE=0.000, o_CLKOUT1=pix5x_clk_pll
            ),
            Instance("BUFG", i_I=pix_clk_pll, o_O=pix_clk),
            Instance("BUFIO", i_I=pix5x_clk_pll, o_O=pix5x_clk),
        ]

        self.clock_domains.cd_pix = ClockDomain("pix")
        self.clock_domains.cd_pix5x = ClockDomain("pix5x", reset_less=True)
        self.comb += [
            self.cd_pix.rst.eq(ResetSignal()), # FIXME
            self.cd_pix.clk.eq(pix_clk),
            self.cd_pix5x.clk.eq(pix5x_clk)
        ]

        reset_timer = WaitTimer(256)
        self.submodules += reset_timer
        self.comb += reset_timer.wait.eq(mmcm_locked)

        # hdmi input
        ctl_valid = Signal(3)
        ctl = [Signal(2) for i in range(3)]
        data_valid = Signal(3)
        data = [Signal(8) for i in range(3)]

        for i in range(3):
            chan = HDMIInputChannel(hdmi_in_data[i])
            self.submodules += chan
            self.comb += [
                chan.reset.eq(~reset_timer.done),
                ctl_valid[i].eq(chan.ctl_valid),
                ctl[i].eq(chan.ctl),
                data_valid[i].eq(chan.data_valid),
                data[i].eq(chan.data)
            ]

        de = Signal()
        hsync = Signal()
        vsync = Signal()
        r = Signal(8)
        g = Signal(8)
        b = Signal(8)

        self.sync.pix += [
            If(ctl_valid[0] & ctl_valid[1] & ctl_valid[2],
                vsync.eq(ctl[0][1]),
                hsync.eq(ctl[0][0]),
                de.eq(0),
                r.eq(0),
                g.eq(0),
                b.eq(0)
            ).Elif(data_valid[0] & data_valid[1] & data_valid[2],
                vsync.eq(0),
                hsync.eq(0),
                de.eq(1),
                r.eq(data[2]),
                g.eq(data[1]),
                b.eq(data[0])
            )
        ]

        # hdmi output
        self.submodules.hdmi_output_clkgen = S7HDMIOutEncoderSerializer(hdmi_out_pads.clk_p, hdmi_out_pads.clk_n, bypass_encoder=True)
        self.submodules.hdmi_output = S7HDMIOutPHY(hdmi_out_pads)

        self.comb += [
            self.hdmi_output_clkgen.data.eq(Signal(10, reset=0b0000011111)),
            self.hdmi_output.sink.valid.eq(1),
            self.hdmi_output.sink.de.eq(de),
            self.hdmi_output.sink.hsync.eq(hsync),
            self.hdmi_output.sink.vsync.eq(vsync),
            self.hdmi_output.sink.r.eq(r),
            self.hdmi_output.sink.g.eq(g),
            self.hdmi_output.sink.b.eq(b)
        ]
        self.comb += hdmi_out_pads.scl.eq(1)

def main():
    platform = nexys_video.Platform()
    hdmi_loopback = HDMILoopback(platform)
    platform.build(hdmi_loopback)

    prog = VivadoProgrammer()
    prog.load_bitstream("build/top.bit")


if __name__ == "__main__":
    main()

