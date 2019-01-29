from migen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litevideo.output.common import *
from litevideo.output.hdmi.encoder import Encoder

# Serializer and Clocking initial configurations come
# from http://hamsterworks.co.nz/.

class S7HDMIOutEncoderSerializer(Module):
    def __init__(self, pad_p, pad_n, bypass_encoder=False):
        if not bypass_encoder:
            self.submodules.encoder = ClockDomainsRenamer("pix")(Encoder())
            self.d, self.c, self.de = self.encoder.d, self.encoder.c, self.encoder.de
            self.data = self.encoder.out
        else:
            self.data = Signal(10)

        # # #

        data = Signal(10)
        if hasattr(pad_p, "inverted"):
            self.comb += data.eq(~self.data)
        else:
            self.comb += data.eq(self.data)

        ce = Signal()
        self.sync.pix += ce.eq(~ResetSignal("pix"))

        shift = Signal(2)
        pad_se = Signal()

        # OSERDESE2 master
        self.specials += [
            Instance("OSERDESE2",
                p_DATA_WIDTH=10, p_TRISTATE_WIDTH=1,
                p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="DDR",
                p_SERDES_MODE="MASTER",

                o_OQ=pad_se,
                i_OCE=ce,
                i_TCE=0,
                i_RST=ResetSignal("pix"),
                i_CLK=ClockSignal("pix5x"), i_CLKDIV=ClockSignal("pix"),
                i_D1=data[0], i_D2=data[1],
                i_D3=data[2], i_D4=data[3],
                i_D5=data[4], i_D6=data[5],
                i_D7=data[6], i_D8=data[7],

                i_SHIFTIN1=shift[0], i_SHIFTIN2=shift[1],
                #o_SHIFTOUT1=, o_SHIFTOUT2=,
            ),
            Instance("OSERDESE2",
                p_DATA_WIDTH=10, p_TRISTATE_WIDTH=1,
                p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="DDR",
                p_SERDES_MODE="SLAVE",

                i_OCE=ce,
                i_TCE=0,
                i_RST=ResetSignal("pix"),
                i_CLK=ClockSignal("pix5x"), i_CLKDIV=ClockSignal("pix"),
                i_D1=0, i_D2=0,
                i_D3=data[8], i_D4=data[9],
                i_D5=0, i_D6=0,
                i_D7=0, i_D8=0,

                i_SHIFTIN1=0, i_SHIFTIN2=0,
                o_SHIFTOUT1=shift[0], o_SHIFTOUT2=shift[1]
            ),
            Instance("OBUFDS", i_I=pad_se, o_O=pad_p, o_OB=pad_n)
        ]


# This assumes a 100MHz base clock
class S7HDMIOutClocking(Module, AutoCSR):
    def __init__(self, pads, external_clocking):
        # TODO: implement external clocking
        self.clock_domains.cd_pix = ClockDomain("pix")
        self.clock_domains.cd_pix5x = ClockDomain("pix5x", reset_less=True)

        self._mmcm_reset = CSRStorage()
        self._mmcm_read = CSR()
        self._mmcm_write = CSR()
        self._mmcm_drdy = CSRStatus()
        self._mmcm_adr = CSRStorage(7)
        self._mmcm_dat_w = CSRStorage(16)
        self._mmcm_dat_r = CSRStatus(16)

        # # #

        mmcm_locked = Signal()
        mmcm_fb = Signal()
        mmcm_clk0 = Signal()
        mmcm_clk1 = Signal()
        mmcm_drdy = Signal()

        self.specials += [
            Instance("MMCME2_ADV",
                p_BANDWIDTH="OPTIMIZED",
                i_RST=self._mmcm_reset.storage, o_LOCKED=mmcm_locked,

                # VCO
                p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=10.0,
                p_CLKFBOUT_MULT_F=30.0, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=2,
                i_CLKIN1=ClockSignal("clk100"), i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,

                # CLK0
                p_CLKOUT0_DIVIDE_F=10.0, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=mmcm_clk0,
                # CLK1
                p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.000, o_CLKOUT1=mmcm_clk1,

                # DRP
                i_DCLK=ClockSignal(),
                i_DWE=self._mmcm_write.re,
                i_DEN=self._mmcm_read.re | self._mmcm_write.re,
                o_DRDY=mmcm_drdy,
                i_DADDR=self._mmcm_adr.storage,
                i_DI=self._mmcm_dat_w.storage,
                o_DO=self._mmcm_dat_r.status
            ),
            Instance("BUFG", i_I=mmcm_clk0, o_O=self.cd_pix.clk),
            Instance("BUFG", i_I=mmcm_clk1, o_O=self.cd_pix5x.clk)
        ]
        self.sync += [
            If(self._mmcm_read.re | self._mmcm_write.re,
                self._mmcm_drdy.status.eq(0)
            ).Elif(mmcm_drdy,
                self._mmcm_drdy.status.eq(1)
            )
        ]
        self.comb += self.cd_pix.rst.eq(~mmcm_locked)
        if hasattr(pads, "clk_p"):
            self.submodules.clk_gen = S7HDMIOutEncoderSerializer(pads.clk_p, pads.clk_n, bypass_encoder=True)
            self.comb += self.clk_gen.data.eq(Signal(10, reset=0b0000011111))
        else:
            self.comb += pads.clk.eq(ClockSignal("pix")) # FIXME: use primitive (ODDR2?)


class S7HDMIOutPHY(Module):
    def __init__(self, pads, mode):
        self.sink = sink = stream.Endpoint(phy_layout(mode))

        # # #

        self.submodules.es0 = S7HDMIOutEncoderSerializer(pads.data0_p, pads.data0_n, mode == "raw")
        self.submodules.es1 = S7HDMIOutEncoderSerializer(pads.data1_p, pads.data1_n, mode == "raw")
        self.submodules.es2 = S7HDMIOutEncoderSerializer(pads.data2_p, pads.data2_n, mode == "raw")

        if mode == "raw":
            self.comb += [
                sink.ready.eq(1),
                self.es0.data.eq(sink.c0),
                self.es1.data.eq(sink.c1),
                self.es2.data.eq(sink.c2)
            ]
        else:
            self.comb += [
                sink.ready.eq(1),
                self.es0.d.eq(sink.b),
                self.es1.d.eq(sink.g),
                self.es2.d.eq(sink.r),
                self.es0.c.eq(Cat(sink.hsync, sink.vsync)),
                self.es1.c.eq(0),
                self.es2.c.eq(0),
                self.es0.de.eq(sink.de),
                self.es1.de.eq(sink.de),
                self.es2.de.eq(sink.de)
            ]
