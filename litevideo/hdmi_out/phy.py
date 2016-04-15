from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import AutoCSR
from litevideo.hdmi_out.format import bpc_phy, phy_layout

from litevideo.csc.ycbcr2rgb import YCbCr2RGB
from litevideo.csc.ycbcr422to444 import YCbCr422to444

from litevideo.phy.s6hdmiout import S6HDMIOutClocking, S6HDMIOutPHY

clocking_cls = {
    "xc6" : S6HDMIOutClocking
}

phy_cls = {
    "xc6" : S6HDMIOutPHY
}

# XXX replace with standard fifo?
class _FIFO(Module):
    def __init__(self, pack_factor):
        self.phy = stream.Endpoint(phy_layout(pack_factor))
        self.busy = Signal()

        self.pix_hsync = Signal()
        self.pix_vsync = Signal()
        self.pix_de = Signal()
        self.pix_y = Signal(bpc_phy)
        self.pix_cb_cr = Signal(bpc_phy)

        # # #

        fifo = ClockDomainsRenamer({"write": "sys", "read": "pix"})(stream.AsyncFIFO(phy_layout(pack_factor), 512))
        self.submodules += fifo
        self.comb += [
            self.phy.connect(fifo.sink),
            self.busy.eq(0)
        ]

        unpack_counter = Signal(max=pack_factor)
        assert(pack_factor & (pack_factor - 1) == 0)  # only support powers of 2
        self.sync.pix += [
            unpack_counter.eq(unpack_counter + 1),
            self.pix_hsync.eq(fifo.source.hsync),
            self.pix_vsync.eq(fifo.source.vsync),
            self.pix_de.eq(fifo.source.de)
        ]
        for i in range(pack_factor):
            pixel = getattr(fifo.source, "p"+str(i))
            self.sync.pix += If(unpack_counter == i,
                self.pix_y.eq(pixel.y),
                self.pix_cb_cr.eq(pixel.cb_cr)
            )
        self.comb += fifo.source.ready.eq(unpack_counter == (pack_factor - 1))



class HDMIOutPHY(Module, AutoCSR):
    def __init__(self, device, pack_factor, pads, external_clocking=None):
        fifo = _FIFO(pack_factor)
        self.submodules += fifo
        self.sink = fifo.phy
        self.busy = fifo.busy

        family = device[:3]

        self.submodules.clocking = clocking_cls[family](pads, external_clocking)

        de_r = Signal()
        self.sync.pix += de_r.eq(fifo.pix_de)

        chroma_upsampler = YCbCr422to444()
        self.submodules += ClockDomainsRenamer("pix")(chroma_upsampler)
        self.comb += [
          chroma_upsampler.sink.valid.eq(fifo.pix_de),
          chroma_upsampler.sink.y.eq(fifo.pix_y),
          chroma_upsampler.sink.cb_cr.eq(fifo.pix_cb_cr)
        ]

        ycbcr2rgb = YCbCr2RGB()
        self.submodules += ClockDomainsRenamer("pix")(ycbcr2rgb)
        self.comb += [
            Record.connect(chroma_upsampler.source, ycbcr2rgb.sink),
            ycbcr2rgb.source.ready.eq(1)
        ]

        # XXX need clean up
        de = fifo.pix_de
        hsync = fifo.pix_hsync
        vsync = fifo.pix_vsync
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