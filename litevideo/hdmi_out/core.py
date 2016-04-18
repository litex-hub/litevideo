from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import AutoCSR
from litex.soc.interconnect import dma_lasmi

from litevideo.spi import IntSequence
from litevideo.hdmi_out.format import bpp, pixel_layout, phy_description
from litevideo.hdmi_out.format import FrameInitiator, VideoTimingGenerator


class HDMIOutCore(Module, AutoCSR):
    def __init__(self, lasmim):
        self.pack_factor = lasmim.dw//bpp
        self.source = stream.Endpoint(phy_description(self.pack_factor))

        # # #

        self.submodules.fi = fi = FrameInitiator(lasmim.aw, self.pack_factor)
        self.submodules.intseq = intseq = IntSequence(lasmim.aw, lasmim.aw)
        self.submodules.dma_reader = dma_reader = dma_lasmi.Reader(lasmim)
        self.submodules.cast = cast = stream.Cast(lasmim.dw,
                                                  pixel_layout(self.pack_factor),
                                                  reverse_to=True)
        self.submodules.vtg = vtg = VideoTimingGenerator(self.pack_factor)

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

            fi.source.ready.eq(vtg.timing.ready),

            # intseq --> dma_reader
            dma_reader.sink.valid.eq(intseq.source.valid),
            dma_reader.sink.address.eq(intseq.source.value),
            intseq.source.ready.eq(dma_reader.sink.ready),

            # dma_reader --> cast
            cast.sink.valid.eq(dma_reader.source.valid),
            cast.sink.payload.raw_bits().eq(dma_reader.source.data),
            dma_reader.source.ready.eq(cast.sink.ready),

            # cast --> vtg
            vtg.pixels.valid.eq(cast.source.valid),
            vtg.pixels.payload.eq(cast.source.payload),
            cast.source.ready.eq(vtg.pixels.ready),

            # vtg --> source
            vtg.phy.connect(self.source)
        ]
