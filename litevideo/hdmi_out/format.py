from litex.gen import *
from litex.gen.genlib.fsm import FSM, NextState

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import CSRStorage

from litevideo.spi import SingleGenerator, MODE_CONTINUOUS

_hbits = 12
_vbits = 12

bpp = 16
bpc = 8
pixel_layout_s = [
    ("cb_cr", bpc),
    ("y", bpc)
]

def pixel_layout(pack_factor):
    return [("p"+str(i), pixel_layout_s) for i in range(pack_factor)]

bpc_phy = 8

def phy_description(pack_factor):
    param_layout = [("hsync", 1), ("vsync", 1), ("de", 1)]
    payload_layout = [("data", 2*bpc_phy*pack_factor)]
    return stream.EndpointDescription(payload_layout, param_layout)


class FrameInitiator(SingleGenerator):
    def __init__(self, bus_aw, pack_factor, ndmas=1):
        h_alignment_bits = log2_int(pack_factor)
        hbits_dyn = _hbits - h_alignment_bits
        bus_alignment_bits = h_alignment_bits + log2_int(bpp//8)
        layout = [
            ("hres", hbits_dyn, 640, h_alignment_bits),
            ("hsync_start", hbits_dyn, 656, h_alignment_bits),
            ("hsync_end", hbits_dyn, 752, h_alignment_bits),
            ("hscan", hbits_dyn, 800, h_alignment_bits),

            ("vres", _vbits, 480),
            ("vsync_start", _vbits, 492),
            ("vsync_end", _vbits, 494),
            ("vscan", _vbits, 525),

            ("length", bus_aw + bus_alignment_bits, 640*480*bpp//8, bus_alignment_bits)
        ]
        layout += [("base"+str(i), bus_aw + bus_alignment_bits, 0, bus_alignment_bits)
            for i in range(ndmas)]
        SingleGenerator.__init__(self, layout, MODE_CONTINUOUS)

    timing_subr = ["hres", "hsync_start", "hsync_end", "hscan",
        "vres", "vsync_start", "vsync_end", "vscan"]

    def dma_subr(self, i=0):
        return ["length", "base"+str(i)]


class VTG(Module):
    def __init__(self, pack_factor):
        hbits_dyn = _hbits - log2_int(pack_factor)
        timing_layout = [
            ("hres", hbits_dyn),
            ("hsync_start", hbits_dyn),
            ("hsync_end", hbits_dyn),
            ("hscan", hbits_dyn),
            ("vres", _vbits),
            ("vsync_start", _vbits),
            ("vsync_end", _vbits),
            ("vscan", _vbits)]
        self.timing = stream.Endpoint(timing_layout)
        self.pixels = stream.Endpoint(pixel_layout(pack_factor))
        self.phy = stream.Endpoint(phy_description(pack_factor))

        # # #

        hactive = Signal()
        vactive = Signal()
        active = Signal()

        hcounter = Signal(hbits_dyn)
        vcounter = Signal(_vbits)

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
