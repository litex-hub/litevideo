import os
import subprocess

from migen import *

from litex.soc.interconnect import wishbone

class FPCIIIHDMI( Module ):
    def __init__( self, platform, bitclk, pads ):
        self.bus = wishbone.Interface()
        self.specials += Instance(
            "wishbone_char",
            i_bitclk = bitclk,
            o_r = pads.data0,
            o_g = pads.data1,
            o_b = pads.data2,
            o_c = pads.clk,
            i_RST_I = ResetSignal(),
            i_CLK_I = ClockSignal(),
            i_ADR_I = self.bus.adr,
            i_DAT_I = self.bus.dat_w,
            o_DAT_O = self.bus.dat_r,
            i_WE_I = self.bus.we,
            i_SEL_I = self.bus.sel,
            i_STB_I = self.bus.stb,
            o_ACK_O = self.bus.ack,
            i_CYC_I = self.bus.cyc )
        platform.add_source( os.path.join( os.path.dirname( __file__ ), "hdmi.v" ) )
        platform.add_source( os.path.join( os.path.dirname( __file__ ), "chargen.v" ) )
        d = os.path.join( "build", platform.name, "gateware" )
        os.makedirs( d, exist_ok=True )
        subprocess.check_call( [ "make", "-C", d, "-f", os.path.join( os.path.dirname( __file__ ), "Makefile" ), "VPATH=" + os.path.dirname( __file__ ) ] )
