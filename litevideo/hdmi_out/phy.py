from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import AutoCSR
from litevideo.hdmi_out.format import bpc_phy, phy_description

from litevideo.csc.ycbcr2rgb import YCbCr2RGB
from litevideo.csc.ycbcr422to444 import YCbCr422to444

from litevideo.phy.s6hdmiout import S6HDMIOutClocking, S6HDMIOutPHY

clocking_cls = {
    "xc6" : S6HDMIOutClocking
}

phy_cls = {
    "xc6" : S6HDMIOutPHY
}

class HDMIOutPHY(Module, AutoCSR):
    def __init__(self, device, pack_factor, pads, external_clocking=None):
        self.sink = stream.Endpoint(phy_description(pack_factor))

        # # #

        family = device[:3]

        self.submodules.clocking = clocking_cls[family](pads, external_clocking)

        fifo = stream.AsyncFIFO(phy_description(pack_factor), 512)
        fifo = ClockDomainsRenamer({"write": "sys", "read": "pix"})(fifo)
        self.submodules += fifo
        converter = stream.StrideConverter(phy_description(pack_factor),
                                           phy_description(1))
        converter = ClockDomainsRenamer("pix")(converter)
        self.submodules += converter
        self.comb += [
            self.sink.connect(fifo.sink),
            fifo.source.connect(converter.sink),
            converter.source.ready.eq(1)
        ]

        de_r = Signal()
        self.sync.pix += de_r.eq(converter.source.de)

        chroma_upsampler = YCbCr422to444()
        self.submodules += ClockDomainsRenamer("pix")(chroma_upsampler)
        self.comb += [
          chroma_upsampler.sink.valid.eq(converter.source.de),
          chroma_upsampler.sink.y.eq(converter.source.data[8:]),
          chroma_upsampler.sink.cb_cr.eq(converter.source.data[:8])
        ]

        ycbcr2rgb = YCbCr2RGB()
        self.submodules += ClockDomainsRenamer("pix")(ycbcr2rgb)
        self.comb += [
            Record.connect(chroma_upsampler.source, ycbcr2rgb.sink),
            ycbcr2rgb.source.ready.eq(1)
        ]

        # XXX need clean up
        de = converter.source.de
        hsync = converter.source.hsync
        vsync = converter.source.vsync
        for i in range(chroma_upsampler.latency +
                       ycbcr2rgb.latency):
            next_de = Signal()
            next_vsync = Signal()
            next_hsync = Signal()
            self.sync.pix += [
                next_de.eq(de),
                next_vsync.eq(vsync),
                next_hsync.eq(hsync),
            ]
            de = next_de
            vsync = next_vsync
            hsync = next_hsync

        self.submodules.hdmi_phy = phy_cls[family](self.clocking.serdesstrobe, pads)
        self.comb += [
            self.hdmi_phy.hsync.eq(hsync),
            self.hdmi_phy.vsync.eq(vsync),
            self.hdmi_phy.de.eq(de),
            self.hdmi_phy.r.eq(ycbcr2rgb.source.r),
            self.hdmi_phy.g.eq(ycbcr2rgb.source.g),
            self.hdmi_phy.b.eq(ycbcr2rgb.source.b)
        ]