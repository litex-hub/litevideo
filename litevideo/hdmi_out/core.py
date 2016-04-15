from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import AutoCSR
from litex.soc.interconnect import dma_lasmi

from litevideo.spi import IntSequence
from litevideo.hdmi_out.format import bpp, phy_layout, FrameInitiator, VTG


class HDMIOutCore(Module, AutoCSR):
    def __init__(self, lasmim):
        self.pack_factor = lasmim.dw//bpp
        self.source = stream.Endpoint(phy_layout(self.pack_factor))

        # # #

        self.submodules.fi = fi = FrameInitiator(lasmim.aw, self.pack_factor)
        self.submodules.intseq = intseq = IntSequence(lasmim.aw, lasmim.aw)
        self.submodules.dma_reader = dma_reader = dma_lasmi.Reader(lasmim)
        self.submodules.vtg = vtg = VTG(self.pack_factor)

        self.comb += [
            # fi --> intseq
            intseq.sink.valid.eq(fi.source.valid),
            intseq.sink.offset.eq(fi.source.base0),
            intseq.sink.maximum.eq(fi.source.length),

            # fi --> vtg
            vtg.timing.valid.eq(fi.source.valid),
            vtg.timing.hres.eq(fi.source.hres),
            vtg.timing.hsync_start.eq(fi.source.hsync_start),
            vtg.timing.hsync_end.eq(fi.source.hsync_end),
            vtg.timing.hscan.eq(fi.source.hscan),
            vtg.timing.vres.eq(fi.source.vres),
            vtg.timing.vsync_start.eq(fi.source.vsync_start),
            vtg.timing.vsync_end.eq(fi.source.vsync_end),
            vtg.timing.vscan.eq(fi.source.vscan),

            fi.source.ready.eq(intseq.sink.ready & vtg.timing.ready),

            # intseq --> dma_reader
            dma_reader.sink.valid.eq(intseq.source.valid),
            dma_reader.sink.address.eq(intseq.source.value),
            intseq.source.ready.eq(dma_reader.sink.ready),

            # dma_reader --> vtg
            vtg.pixels.valid.eq(dma_reader.source.valid),
            vtg.pixels.payload.raw_bits().eq(dma_reader.source.data),
            dma_reader.source.ready.eq(vtg.pixels.ready),

            # vtg --> source
            vtg.phy.connect(self.source)
        ]
