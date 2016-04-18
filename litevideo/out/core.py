from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import AutoCSR
from litex.soc.interconnect import dma_lasmi

from litevideo.csc.ycbcr2rgb import YCbCr2RGB
from litevideo.csc.ycbcr422to444 import YCbCr422to444

from litevideo.spi import IntSequence, SingleGenerator, MODE_CONTINUOUS

from litevideo.out.common import *
from litevideo.out.hdmi.s6 import S6HDMIOutClocking, S6HDMIOutPHY


class FrameInitiator(SingleGenerator):
    def __init__(self, bus_aw, pack_factor, ndmas=1):
        h_alignment_bits = log2_int(pack_factor)
        hbits_dyn = hbits - h_alignment_bits
        bus_alignment_bits = h_alignment_bits + log2_int(bpp//8)
        layout = [
            ("hres", hbits_dyn, 640, h_alignment_bits),
            ("hsync_start", hbits_dyn, 656, h_alignment_bits),
            ("hsync_end", hbits_dyn, 752, h_alignment_bits),
            ("hscan", hbits_dyn, 800, h_alignment_bits),

            ("vres", vbits, 480),
            ("vsync_start", vbits, 492),
            ("vsync_end", vbits, 494),
            ("vscan", vbits, 525),

            ("length", bus_aw + bus_alignment_bits, 640*480*bpp//8, bus_alignment_bits)
        ]
        layout += [("base"+str(i), bus_aw + bus_alignment_bits, 0, bus_alignment_bits)
            for i in range(ndmas)]
        SingleGenerator.__init__(self, layout, MODE_CONTINUOUS)

    timing_subr = ["hres", "hsync_start", "hsync_end", "hscan",
        "vres", "vsync_start", "vsync_end", "vscan"]

    def dma_subr(self, i=0):
        return ["length", "base"+str(i)]


class TimingGenerator(Module):
    def __init__(self, pack_factor):
        hbits_dyn = hbits - log2_int(pack_factor)
        timing_layout = [
            ("hres", hbits_dyn),
            ("hsync_start", hbits_dyn),
            ("hsync_end", hbits_dyn),
            ("hscan", hbits_dyn),
            ("vres", vbits),
            ("vsync_start", vbits),
            ("vsync_end", vbits),
            ("vscan", vbits)]
        self.timing = stream.Endpoint(timing_layout)
        self.pixels = stream.Endpoint(pixel_layout(pack_factor))
        self.phy = stream.Endpoint(phy_description(pack_factor))

        # # #

        hactive = Signal()
        vactive = Signal()
        active = Signal()

        hcounter = Signal(hbits_dyn)
        vcounter = Signal(vbits)

        skip = bpc - bpc_phy
        self.comb += [
            active.eq(hactive & vactive),
            If(active,
                self.phy.valid.eq(1),
                self.phy.de.eq(1),
                self.phy.payload.raw_bits().eq(self.pixels.payload.raw_bits())
            ),
            self.pixels.ready.eq(self.phy.ready & active)
        ]

        load_timing = Signal()
        tr = Record(timing_layout)
        self.sync += If(load_timing, tr.eq(self.timing.payload))

        generate_en = Signal()
        generate_frame_done = Signal()
        self.sync += [
            generate_frame_done.eq(0),
            If(generate_en,
                hcounter.eq(hcounter + 1),

                If(hcounter == 0, hactive.eq(1)),
                If(hcounter == tr.hres, hactive.eq(0)),
                If(hcounter == tr.hsync_start, self.phy.hsync.eq(1)),
                If(hcounter == tr.hsync_end, self.phy.hsync.eq(0)),
                If(hcounter == tr.hscan,
                    hcounter.eq(0),
                    If(vcounter == tr.vscan,
                        vcounter.eq(0),
                        generate_frame_done.eq(1)
                    ).Else(
                        vcounter.eq(vcounter + 1)
                    )
                ),

                If(vcounter == 0, vactive.eq(1)),
                If(vcounter == tr.vres, vactive.eq(0)),
                If(vcounter == tr.vsync_start, self.phy.vsync.eq(1)),
                If(vcounter == tr.vsync_end, self.phy.vsync.eq(0))
            )
        ]

        self.submodules.fsm = FSM()
        self.fsm.act("GET_TIMING",
            self.timing.ready.eq(1),
            load_timing.eq(1),
            If(self.timing.valid,
                NextState("GENERATE")
            )
        )
        self.fsm.act("GENERATE",
            If(~active | self.pixels.valid,
                self.phy.valid.eq(1),
                If(self.phy.ready, generate_en.eq(1))
            ),
            If(generate_frame_done,
                NextState("GET_TIMING")
            )
        )


clocking_cls = {
    "xc6" : S6HDMIOutClocking
}

phy_cls = {
    "xc6" : S6HDMIOutPHY
}

class Driver(Module, AutoCSR):
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


class VideoOutCore(Module, AutoCSR):
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
        self.submodules.vtg = vtg = TimingGenerator(self.pack_factor)

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


class VideoOut(Module, AutoCSR):
    def __init__(self, device, pads, lasmim, external_clocking=None):
        self.submodules.core = VideoOutCore(lasmim)
        self.submodules.driver = Driver(device,
                                        self.core.pack_factor,
                                        pads,
                                        external_clocking)
        self.comb += self.core.source.connect(self.driver.sink)
