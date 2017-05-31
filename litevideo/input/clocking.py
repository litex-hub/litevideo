from litex.gen import *
from litex.gen.genlib.cdc import MultiReg
from litex.gen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.interconnect.csr import *


class S6Clocking(Module, AutoCSR):
    def __init__(self, pads):
        self._pll_reset = CSRStorage(reset=1)
        self._locked = CSRStatus()

        # DRP
        self._pll_adr = CSRStorage(5)
        self._pll_dat_r = CSRStatus(16)
        self._pll_dat_w = CSRStorage(16)
        self._pll_read = CSR()
        self._pll_write = CSR()
        self._pll_drdy = CSRStatus()

        self.locked = Signal()
        self.serdesstrobe = Signal()
        self.clock_domains._cd_pix = ClockDomain()
        self.clock_domains._cd_pix2x = ClockDomain()
        self.clock_domains._cd_pix10x = ClockDomain(reset_less=True)

        # # #

        self.clk_input = Signal()
        self.specials += Instance("IBUFDS", name="hdmi_in_ibufds",
                                  i_I=pads.clk_p, i_IB=pads.clk_n,
                                  o_O=self.clk_input)

        clkfbout = Signal()
        pll_locked = Signal()
        pll_clk0 = Signal()
        pll_clk1 = Signal()
        pll_clk2 = Signal()
        pll_drdy = Signal()
        self.sync += If(self._pll_read.re | self._pll_write.re,
            self._pll_drdy.status.eq(0)
        ).Elif(pll_drdy,
            self._pll_drdy.status.eq(1)
        )
        self.specials += [
            Instance("PLL_ADV",
                name="hdmi_in_pll_adv",
                p_CLKFBOUT_MULT=10,
                p_CLKOUT0_DIVIDE=1,   # pix10x
                p_CLKOUT1_DIVIDE=5,   # pix2x
                p_CLKOUT2_DIVIDE=10,  # pix
                p_COMPENSATION="INTERNAL",

                i_CLKINSEL=1,
                i_CLKIN1=self.clk_input,
                o_CLKOUT0=pll_clk0, o_CLKOUT1=pll_clk1, o_CLKOUT2=pll_clk2,
                o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbout,
                o_LOCKED=pll_locked, i_RST=self._pll_reset.storage,

                i_DADDR=self._pll_adr.storage,
                o_DO=self._pll_dat_r.status,
                i_DI=self._pll_dat_w.storage,
                i_DEN=self._pll_read.re | self._pll_write.re,
                i_DWE=self._pll_write.re,
                o_DRDY=pll_drdy,
                i_DCLK=ClockSignal())
        ]

        locked_async = Signal()
        self.specials += [
            Instance("BUFPLL", name="hdmi_in_bufpll", p_DIVIDE=5,
                i_PLLIN=pll_clk0, i_GCLK=ClockSignal("pix2x"), i_LOCKED=pll_locked,
                o_IOCLK=self._cd_pix10x.clk, o_LOCK=locked_async, o_SERDESSTROBE=self.serdesstrobe),
            Instance("BUFG", name="hdmi_in_pix2x_bufg", i_I=pll_clk1, o_O=self._cd_pix2x.clk),
            Instance("BUFG", name="hdmi_in_pix_bufg", i_I=pll_clk2, o_O=self._cd_pix.clk),
            MultiReg(locked_async, self.locked, "sys")
        ]
        self.comb += self._locked.status.eq(self.locked)

        self.specials += [
            AsyncResetSynchronizer(self.cd_pix, ~locked_async),
            AsyncResetSynchronizer(self.cd_pix2x, ~locked_async),
        ]


class S7Clocking(Module, AutoCSR):
    def __init__(self, pads):
        self._mmcm_reset = CSRStorage()
        self._locked = CSRStatus()

        self.locked = Signal()
        self.clock_domains.cd_pix = ClockDomain()
        self.clock_domains.cd_pix1p25x = ClockDomain()
        self.clock_domains.cd_pix5x = ClockDomain(reset_less=True)

        # # #

        self.clk_input = Signal()
        clk_input_bufg = Signal()
        self.specials += [
            Instance("IBUFDS", name="hdmi_in_ibufds",
                i_I=pads.clk_p, i_IB=pads.clk_n,
                o_O=self.clk_input),
            Instance("BUFG", i_I=self.clk_input, o_O=clk_input_bufg)
        ]

        mmcm_fb = Signal()
        mmcm_locked = Signal()
        mmcm_clk0 = Signal()
        mmcm_clk1 = Signal()
        mmcm_clk2 = Signal()
        self.specials += [
            Instance("MMCME2_ADV",
                p_BANDWIDTH="OPTIMIZED", i_RST=self._mmcm_reset.storage, o_LOCKED=mmcm_locked,

                # VCO
                p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=13.4, # 720p60 / 74.25Mhz pixel clock
                p_CLKFBOUT_MULT_F=10.0, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=1,
                i_CLKIN1=self.clk_input, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,

                # pix clk
                p_CLKOUT0_DIVIDE_F=10, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=mmcm_clk0,
                # pix1p25x clk
                p_CLKOUT1_DIVIDE=8, p_CLKOUT1_PHASE=0.000, o_CLKOUT1=mmcm_clk1,
                # pix5x clk
                p_CLKOUT2_DIVIDE=2, p_CLKOUT2_PHASE=0.000, o_CLKOUT2=mmcm_clk2,
            ),
            Instance("BUFG", i_I=mmcm_clk0, o_O=self.cd_pix.clk),
            Instance("BUFG", i_I=mmcm_clk1, o_O=self.cd_pix1p25x.clk),
            Instance("BUFG",i_I=mmcm_clk2, o_O=self.cd_pix5x.clk),
        ]
        self.specials += MultiReg(mmcm_locked, self.locked, "sys")
        self.comb += self._locked.status.eq(self.locked)

        self.specials += [
            AsyncResetSynchronizer(self.cd_pix, ~mmcm_locked),
            AsyncResetSynchronizer(self.cd_pix1p25x, ~mmcm_locked),
        ]
