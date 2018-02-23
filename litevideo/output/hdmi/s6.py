from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litevideo.output.common import *
from litevideo.output.hdmi.encoder import Encoder


# This assumes a 50MHz base clock
class S6HDMIOutClocking(Module, AutoCSR):
    def __init__(self, pads, external_clocking, max_pix_clk=100e6):
        if external_clocking is None:
            self._cmd_data = CSRStorage(10)
            self._send_cmd_data = CSR()
            self._send_go = CSR()
            self._status = CSRStatus(4)
            self._max_pix_clk = CSRConstant(max_pix_clk)

            self.clock_domains.cd_pix = ClockDomain(reset_less=True)
            self._pll_reset = CSRStorage()
            self._pll_adr = CSRStorage(5)
            self._pll_dat_r = CSRStatus(16)
            self._pll_dat_w = CSRStorage(16)
            self._pll_read = CSR()
            self._pll_write = CSR()
            self._pll_drdy = CSRStatus()

            self.clock_domains.cd_pix2x = ClockDomain(reset_less=True)
            self.clock_domains.cd_pix10x = ClockDomain(reset_less=True)
            self.serdesstrobe = Signal()

            # # #

            # Generate 1x pixel clock
            clk_pix_unbuffered = Signal()
            pix_progdata = Signal()
            pix_progen = Signal()
            pix_progdone = Signal()

            pix_locked = Signal()

            clkfx_md_max = max(2.0/4.0, max_pix_clk/50e6)
            self._clkfx_md_max_1000 = CSRConstant(clkfx_md_max*1000.0)
            self.specials += Instance("DCM_CLKGEN",
                name="hdmi_out_dcm_clkgen",

                # parameters
                p_SPREAD_SPECTRUM="NONE",
                p_STARTUP_WAIT="FALSE",

                # reset
                i_FREEZEDCM=0,
                i_RST=ResetSignal(),

                # input
                i_CLKIN=ClockSignal("base50"),
                p_CLKIN_PERIOD=20.0,

                # output
                p_CLKFXDV_DIVIDE=2,
                p_CLKFX_MULTIPLY=2,
                p_CLKFX_DIVIDE=4,
                p_CLKFX_MD_MAX=clkfx_md_max,
                o_CLKFX=clk_pix_unbuffered,
                o_LOCKED=pix_locked,

                # programming interface
                i_PROGCLK=ClockSignal(),
                i_PROGDATA=pix_progdata,
                i_PROGEN=pix_progen,
                o_PROGDONE=pix_progdone
            )

            remaining_bits = Signal(max=11)
            transmitting = Signal()
            self.comb += transmitting.eq(remaining_bits != 0)
            sr = Signal(10)
            self.sync += [
                If(self._send_cmd_data.re,
                    remaining_bits.eq(10),
                    sr.eq(self._cmd_data.storage)
                ).Elif(transmitting,
                    remaining_bits.eq(remaining_bits - 1),
                    sr.eq(sr[1:])
                )
            ]
            self.comb += [
                pix_progdata.eq(transmitting & sr[0]),
                pix_progen.eq(transmitting | self._send_go.re)
            ]

            # enforce gap between commands
            busy_counter = Signal(max=14)
            busy = Signal()
            self.comb += busy.eq(busy_counter != 0)
            self.sync += If(self._send_cmd_data.re,
                    busy_counter.eq(13)
                ).Elif(busy,
                    busy_counter.eq(busy_counter - 1)
                )

            mult_locked = Signal()
            self.comb += self._status.status.eq(Cat(busy, pix_progdone, pix_locked, mult_locked))

            # Clock multiplication and buffering
            # Route unbuffered 1x pixel clock to PLL
            # Generate 1x, 2x and 10x IO pixel clocks
            clkfbout = Signal()
            pll_locked = Signal()
            pll0_pix10x = Signal()
            pll1_pix2x = Signal()
            pll2_pix = Signal()
            locked_async = Signal()
            pll_drdy = Signal()
            self.sync += If(self._pll_read.re | self._pll_write.re,
                self._pll_drdy.status.eq(0)
            ).Elif(pll_drdy,
                self._pll_drdy.status.eq(1)
            )
            self.specials += [
                Instance("PLL_ADV",
                         name="hdmi_out_pll_adv",
                         p_CLKFBOUT_MULT=10,
                         p_CLKOUT0_DIVIDE=1,   # pix10x
                         p_CLKOUT1_DIVIDE=5,   # pix2x
                         p_CLKOUT2_DIVIDE=10,  # pix
                         p_COMPENSATION="INTERNAL",

                         i_CLKINSEL=1,
                         i_CLKIN1=clk_pix_unbuffered,
                         o_CLKOUT0=pll0_pix10x, o_CLKOUT1=pll1_pix2x, o_CLKOUT2=pll2_pix,
                         o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbout,
                         o_LOCKED=pll_locked,
                         i_RST=~pix_locked | self._pll_reset.storage,

                         i_DADDR=self._pll_adr.storage,
                         o_DO=self._pll_dat_r.status,
                         i_DI=self._pll_dat_w.storage,
                         i_DEN=self._pll_read.re | self._pll_write.re,
                         i_DWE=self._pll_write.re,
                         o_DRDY=pll_drdy,
                         i_DCLK=ClockSignal()),
                Instance("BUFPLL", name="hdmi_out_bufpll", p_DIVIDE=5,
                         i_PLLIN=pll0_pix10x, i_GCLK=ClockSignal("pix2x"), i_LOCKED=pll_locked,
                         o_IOCLK=self.cd_pix10x.clk, o_LOCK=locked_async, o_SERDESSTROBE=self.serdesstrobe),
                Instance("BUFG", name="hdmi_out_pix2x_bufg", i_I=pll1_pix2x, o_O=self.cd_pix2x.clk),
                Instance("BUFG", name="hdmi_out_pix_bufg", i_I=pll2_pix, o_O=self.cd_pix.clk),
                MultiReg(locked_async, mult_locked, "sys")
            ]

            self.pll0_pix10x = pll0_pix10x
            self.pll1_pix2x = pll1_pix2x
            self.pll2_pix = pll2_pix
            self.pll_locked = pll_locked

        else:
            self.clock_domains.cd_pix = ClockDomain(reset_less=True)
            self.specials +=  Instance("BUFG", name="hdmi_out_pix_bufg", i_I=external_clocking.pll2_pix, o_O=self.cd_pix.clk)
            self.clock_domains.cd_pix2x = ClockDomain(reset_less=True)
            self.clock_domains.cd_pix10x = ClockDomain(reset_less=True)
            self.serdesstrobe = Signal()
            self.specials += [
                Instance("BUFG", name="hdmi_out_pix2x_bufg", i_I=external_clocking.pll1_pix2x, o_O=self.cd_pix2x.clk),
                Instance("BUFPLL", name="hdmi_out_bufpll", p_DIVIDE=5,
                         i_PLLIN=external_clocking.pll0_pix10x, i_GCLK=self.cd_pix2x.clk, i_LOCKED=external_clocking.pll_locked,
                         o_IOCLK=self.cd_pix10x.clk, o_SERDESSTROBE=self.serdesstrobe),
            ]

        # Drive HDMI clock pads
        hdmi_clk_se = Signal()
        self.specials += Instance("ODDR2",
                                  p_DDR_ALIGNMENT="NONE", p_INIT=0, p_SRTYPE="SYNC",
                                  o_Q=hdmi_clk_se,
                                  i_C0=ClockSignal("pix"),
                                  i_C1=~ClockSignal("pix"),
                                  i_CE=1,
                                  i_D0=not hasattr(pads.clk_p, "inverted"),
                                  i_D1=hasattr(pads.clk_p, "inverted"),
                                  i_R=0, i_S=0)
        if hasattr(pads, "clk_p"):
            self.specials += Instance("OBUFDS", i_I=hdmi_clk_se,
                                      o_O=pads.clk_p, o_OB=pads.clk_n)
        else:
            self.comb += pads.clk.eq(hdmi_clk_se)


class _S6HDMIOutEncoderSerializer(Module):
    def __init__(self, serdesstrobe, pad_p, pad_n, bypass_encoder=False):
        if not bypass_encoder:
            self.submodules.encoder = ClockDomainsRenamer("pix")(Encoder())
            self.d, self.c, self.de = self.encoder.d, self.encoder.c, self.encoder.de
            self.data = self.encoder.out
        else:
            self.data = Signal(10)

        # # #

        # 2X soft serialization
        ed_2x_pol = Signal(5)
        ed_2x = Signal(5)
        self.sync.pix2x += ed_2x_pol.eq(Mux(ClockSignal("pix"), self.data[:5], self.data[5:]))
        if hasattr(pad_p, "inverted"):
            self.comb += ed_2x.eq(~ed_2x_pol)
        else:
            self.comb += ed_2x.eq(ed_2x_pol)

        # 5X hard serialization
        cascade_di = Signal()
        cascade_do = Signal()
        cascade_ti = Signal()
        cascade_to = Signal()
        pad_se = Signal()
        self.specials += [
            Instance("OSERDES2",
                     p_DATA_WIDTH=5, p_DATA_RATE_OQ="SDR", p_DATA_RATE_OT="SDR",
                     p_SERDES_MODE="MASTER", p_OUTPUT_MODE="DIFFERENTIAL",

                     o_OQ=pad_se,
                     i_OCE=1, i_IOCE=serdesstrobe, i_RST=0,
                     i_CLK0=ClockSignal("pix10x"), i_CLK1=0, i_CLKDIV=ClockSignal("pix2x"),
                     i_D1=ed_2x[4], i_D2=0, i_D3=0, i_D4=0,
                     i_T1=0, i_T2=0, i_T3=0, i_T4=0,
                     i_TRAIN=0, i_TCE=1,
                     i_SHIFTIN1=1, i_SHIFTIN2=1,
                     i_SHIFTIN3=cascade_do, i_SHIFTIN4=cascade_to,
                     o_SHIFTOUT1=cascade_di, o_SHIFTOUT2=cascade_ti),
            Instance("OSERDES2",
                     p_DATA_WIDTH=5, p_DATA_RATE_OQ="SDR", p_DATA_RATE_OT="SDR",
                     p_SERDES_MODE="SLAVE", p_OUTPUT_MODE="DIFFERENTIAL",

                     i_OCE=1, i_IOCE=serdesstrobe, i_RST=0,
                     i_CLK0=ClockSignal("pix10x"), i_CLK1=0, i_CLKDIV=ClockSignal("pix2x"),
                     i_D1=ed_2x[0], i_D2=ed_2x[1], i_D3=ed_2x[2], i_D4=ed_2x[3],
                     i_T1=0, i_T2=0, i_T3=0, i_T4=0,
                     i_TRAIN=0, i_TCE=1,
                     i_SHIFTIN1=cascade_di, i_SHIFTIN2=cascade_ti,
                     i_SHIFTIN3=1, i_SHIFTIN4=1,
                     o_SHIFTOUT3=cascade_do, o_SHIFTOUT4=cascade_to),
            Instance("OBUFDS", i_I=pad_se, o_O=pad_p, o_OB=pad_n)
        ]


class S6HDMIOutPHY(Module):
    def __init__(self, pads, mode):
        self.serdesstrobe = Signal()
        self.sink = sink = stream.Endpoint(phy_layout(mode))

        # # #

        self.submodules.es0 = _S6HDMIOutEncoderSerializer(self.serdesstrobe, pads.data0_p, pads.data0_n, mode == "raw")
        self.submodules.es1 = _S6HDMIOutEncoderSerializer(self.serdesstrobe, pads.data1_p, pads.data1_n, mode == "raw")
        self.submodules.es2 = _S6HDMIOutEncoderSerializer(self.serdesstrobe, pads.data2_p, pads.data2_n, mode == "raw")

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
