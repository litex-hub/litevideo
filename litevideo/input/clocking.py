from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.interconnect.csr import *


class S6Clocking(Module, AutoCSR):
    def __init__(self, pads, clkin_freq=None, split_clocking=None):
        assert not bool(split_clocking), "Can't use split_clocking with S6Clocking"
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
        self.clock_domains._cd_pix_o = ClockDomain()
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
            AsyncResetSynchronizer(self._cd_pix, ~locked_async),
            AsyncResetSynchronizer(self._cd_pix2x, ~locked_async),
        ]
        self.comb += self._cd_pix_o.clk.eq(self._cd_pix.clk)


class S7Clocking(Module, AutoCSR):
    def __init__(self, pads, clkin_freq=148.5e6, split_clocking=False):
        self._mmcm_reset = CSRStorage(reset=1)
        self._locked = CSRStatus()

        # DRP
        self._mmcm_read = CSR()
        self._mmcm_write = CSR()
        self._mmcm_drdy = CSRStatus()
        self._mmcm_adr = CSRStorage(7)
        self._mmcm_dat_w = CSRStorage(16)
        self._mmcm_dat_r = CSRStatus(16)

        self.locked = Signal()
        self.clock_domains.cd_pix = ClockDomain()
        self.clock_domains.cd_pix_o = ClockDomain()
        self.clock_domains.cd_pix1p25x = ClockDomain()
        self.clock_domains.cd_pix5x = ClockDomain(reset_less=True)
        self.clock_domains.cd_pix5x_inv = ClockDomain(reset_less=True)
        self.clock_domains.cd_pix5x_o = ClockDomain(reset_less=True)
        self.clock_domains.cd_pix5x_inv_o = ClockDomain(reset_less=True)

        if split_clocking:
            self._mmcm_write_o = CSR()
            self._mmcm_read_o = CSR()
            self._mmcm_dat_o_r = CSRStatus(16)
            self._mmcm_drdy_o = CSRStatus()

        # # #

        assert clkin_freq in [74.25e6, 148.5e6]
        self.clk_input = Signal()
        clk_input_bufr = Signal()
        if hasattr(pads.clk_p, "inverted"):
            self.specials += Instance("IBUFDS_DIFF_OUT",
                name="hdmi_in_ibufds",
                i_I=pads.clk_p, i_IB=pads.clk_n,
                o_OB=self.clk_input)
        else:
            self.specials += Instance("IBUFDS_DIFF_OUT",
                name="hdmi_in_ibufds",
                i_I=pads.clk_p, i_IB=pads.clk_n,
                o_O=self.clk_input)
        self.specials += Instance("BUFR", i_I=self.clk_input, o_O=clk_input_bufr)

        mmcm_fb = Signal()
        mmcm_locked = Signal()
        mmcm_clk0 = Signal()
        mmcm_clk1 = Signal()
        mmcm_clk2 = Signal()
        mmcm_clk3 = Signal()
        mmcm_drdy = Signal()
        mmcm_fb_o = Signal() # this should be harmless in single domain, but essential for split

        self.specials += [
            Instance("MMCME2_ADV",
                p_BANDWIDTH="OPTIMIZED", i_RST=self._mmcm_reset.storage, o_LOCKED=mmcm_locked,

                # VCO
                p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=6.734,
                p_CLKFBOUT_MULT_F=5.0, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=1,
                # p_SS_EN="TRUE", p_SS_MODE="CENTER_LOW",
                i_CLKIN1=clk_input_bufr, i_CLKFBIN=mmcm_fb_o, o_CLKFBOUT=mmcm_fb,

                # pix clk
                p_CLKOUT0_DIVIDE_F=5, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=mmcm_clk0,
                # pix1p25x clk
                p_CLKOUT1_DIVIDE=4, p_CLKOUT1_PHASE=0.000, o_CLKOUT1=mmcm_clk1,
                # pix5x clk
                p_CLKOUT2_DIVIDE=1, p_CLKOUT2_PHASE=0.000, o_CLKOUT2=mmcm_clk2,
                # pix5x inv clk
                p_CLKOUT3_DIVIDE=1, p_CLKOUT3_PHASE=180.000, o_CLKOUT3=mmcm_clk3,

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
            Instance("BUFG", i_I=mmcm_clk1, o_O=self.cd_pix1p25x.clk),
            Instance("BUFG", i_I=mmcm_clk2, o_O=self.cd_pix5x.clk),
            Instance("BUFG", i_I=mmcm_clk3, o_O=self.cd_pix5x_inv.clk),
            Instance("BUFG", i_I=mmcm_fb, o_O=mmcm_fb_o), # compensate this delay to minimize phase offset with slave
        ]

        self.sync += [
            If(self._mmcm_read.re | self._mmcm_write.re,
                self._mmcm_drdy.status.eq(0)
            ).Elif(mmcm_drdy,
                self._mmcm_drdy.status.eq(1)
            )
        ]

        if split_clocking:
            mmcm_fb2_o = Signal()
            mmcm_locked_o = Signal()
            mmcm_clk0_o = Signal()
            mmcm_clk2_o = Signal()
            mmcm_clk3_o = Signal()
            mmcm_drdy_o = Signal()

            self.specials += [
                Instance("PLLE2_ADV",
                    p_BANDWIDTH="LOW", i_RST=self._mmcm_reset.storage, o_LOCKED=mmcm_locked_o,

                    # VCO
                    p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=6.734,
                    p_CLKFBOUT_MULT=10, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=1, # PLL range is 800-1866 MHz, unlike MMCM which is 600-1440 MHz
                    i_CLKIN1=mmcm_clk0,  # uncompensated delay for best phase match between master/slave
                    i_CLKFBIN=mmcm_fb2_o, o_CLKFBOUT=mmcm_fb2_o,

                    # pix clk
                    p_CLKOUT0_DIVIDE=10, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=mmcm_clk0_o,
                    p_CLKOUT2_DIVIDE=2, p_CLKOUT2_PHASE=0.000, o_CLKOUT2=mmcm_clk2_o,
                    p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=180.000, o_CLKOUT3=mmcm_clk3_o,

                    # DRP
                    i_DCLK=ClockSignal(),
                    i_DWE=self._mmcm_write_o.re,
                    i_DEN=self._mmcm_read_o.re | self._mmcm_write_o.re,
                    o_DRDY=mmcm_drdy_o,
                    i_DADDR=self._mmcm_adr.storage,
                    i_DI=self._mmcm_dat_w.storage,
                    o_DO=self._mmcm_dat_o_r.status
                ),
                Instance("BUFG", i_I=mmcm_clk0_o, o_O=self.cd_pix_o.clk),
                Instance("BUFG", i_I=mmcm_clk2_o, o_O=self.cd_pix5x_o.clk), # was BUFIO...
                Instance("BUFG", i_I=mmcm_clk3_o, o_O=self.cd_pix5x_inv_o.clk),
            ]

            self.sync += [
                If(self._mmcm_read_o.re | self._mmcm_write_o.re,
                    self._mmcm_drdy_o.status.eq(0)
                ).Elif(mmcm_drdy_o,
                    self._mmcm_drdy_o.status.eq(1)
                )
            ]
        else:
            self.comb += [
                self.cd_pix_o.clk.eq(self.cd_pix.clk),
                self.cd_pix5x_o.clk.eq(self.cd_pix5x.clk),
                self.cd_pix5x_inv_o.clk.eq(self.cd_pix5x_inv.clk),
            ]

        self.specials += MultiReg(mmcm_locked, self.locked, "sys")
        self.comb += self._locked.status.eq(self.locked)

        self.specials += [
            AsyncResetSynchronizer(self.cd_pix, ~mmcm_locked),
            AsyncResetSynchronizer(self.cd_pix1p25x, ~mmcm_locked),
        ]

        if split_clocking:
            self.specials += AsyncResetSynchronizer(self.cd_pix_o, ~mmcm_locked_o)
        else:
            self.comb += self.cd_pix_o.rst.eq(self.cd_pix.rst)

