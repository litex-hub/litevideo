from litex.gen import *

from litex.soc.interconnect.csr import AutoCSR
from litex.soc.interconnect import dma_lasmi

from litevideo.spi import IntSequence
from litevideo.hdmi_out.format import bpp, pixel_layout, FrameInitiator, VTG
from litevideo.hdmi_out.phy import Driver


class HDMIOut(Module, AutoCSR):
    def __init__(self, pads, lasmim, external_clocking=None):
        pack_factor = lasmim.dw//bpp

        self.submodules.fi = FrameInitiator(lasmim.aw, pack_factor)

        self.submodules.intseq = IntSequence(lasmim.aw, lasmim.aw)
        self.submodules.dma_reader = dma_lasmi.Reader(lasmim)
        self.comb += [
            self.intseq.sink.valid.eq(self.fi.source.valid),
            self.intseq.sink.offset.eq(self.fi.source.base0),
            self.intseq.sink.maximum.eq(self.fi.source.length),
            self.dma_reader.address.valid.eq(self.intseq.source.valid),
            self.dma_reader.address.a.eq(self.intseq.source.value),
            self.intseq.source.ready.eq(self.dma_reader.address.ready),
        ]

        self.submodules.vtg = VTG(pack_factor)
        self.comb += [
            self.vtg.timing.valid.eq(self.fi.source.valid),
            self.vtg.timing.hres.eq(self.fi.source.hres),
            self.vtg.timing.hsync_start.eq(self.fi.source.hsync_start),
            self.vtg.timing.hsync_end.eq(self.fi.source.hsync_end),
            self.vtg.timing.hscan.eq(self.fi.source.hscan),
            self.vtg.timing.vres.eq(self.fi.source.vres),
            self.vtg.timing.vsync_start.eq(self.fi.source.vsync_start),
            self.vtg.timing.vsync_end.eq(self.fi.source.vsync_end),
            self.vtg.timing.vscan.eq(self.fi.source.vscan),

            self.vtg.pixels.valid.eq(self.dma_reader.data.valid),
            self.dma_reader.data.ready.eq(self.vtg.pixels.ready),
            self.vtg.pixels.payload.raw_bits().eq(self.dma_reader.data.d)
        ]

        self.comb += self.fi.source.ready.eq(self.intseq.sink.ready & self.vtg.timing.ready)

        self.submodules.driver = Driver(pack_factor, pads, external_clocking)
        self.comb += self.vtg.phy.connect(self.driver.phy)
