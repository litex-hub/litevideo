from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litedram.frontend.dma import LiteDRAMDMAReader

from litevideo.output.common import *
from litevideo.output.hdmi.s6 import S6HDMIOutClocking, S6HDMIOutPHY
from litevideo.output.hdmi.s7 import S7HDMIOutClocking, S7HDMIOutPHY


class Initiator(Module, AutoCSR):
    """Initiator

    Generates the H/V and DMA parameters of a frame.
    """
    def __init__(self, cd):
        self.source = stream.Endpoint(frame_parameter_layout +
                                      frame_dma_layout)

        # # #

        cdc = stream.AsyncFIFO(self.source.description, 4)
        cdc = ClockDomainsRenamer({"write": "sys",
                                   "read": cd})(cdc)
        self.submodules += cdc

        self.enable = CSRStorage()
        for name, width in frame_parameter_layout + frame_dma_layout:
            setattr(self, name, CSRStorage(width, name=name))
            self.comb += getattr(cdc.sink, name).eq(getattr(self, name).storage)
        self.comb += cdc.sink.valid.eq(self.enable.storage)
        self.comb += cdc.source.connect(self.source)


class DMAReader(Module, AutoCSR):
    """DMA reader

    Generates the data stream of a frame.
    """
    def __init__(self, dram_port, fifo_depth=512):
        self.sink = sink = stream.Endpoint(frame_dma_layout)
        self.source = source = stream.Endpoint([("data", dram_port.dw)])

        # # #

        self.submodules.dma = LiteDRAMDMAReader(dram_port, fifo_depth, True)
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        shift = log2_int(dram_port.dw//8)
        base = Signal(dram_port.aw)
        length = Signal(dram_port.aw)
        offset = Signal(dram_port.aw)
        self.comb += [
            base.eq(sink.base[shift:]),
            length.eq(sink.length[shift:])
        ]

        fsm.act("IDLE",
            If(sink.valid,
                NextValue(offset, 0),
                NextState("READ")
            )
        )
        fsm.act("READ",
            self.dma.sink.valid.eq(1),
            If(self.dma.sink.ready,
                NextValue(offset, offset + 1),
                If(offset == (length - 1),
                    self.sink.ready.eq(1),
                    NextState("IDLE")
                )
            )
        )
        self.comb += [
            self.dma.sink.address.eq(base + offset),
            self.dma.source.connect(self.source)
        ]


class TimingGenerator(Module):
    """Timing Generator

    Generates the H/V timings of a frame.
    """
    def __init__(self):
        self.sink = sink = stream.Endpoint(frame_parameter_layout)
        self.source = source = stream.Endpoint(frame_timing_layout)

        # # #

        hactive = Signal()
        vactive = Signal()
        active = Signal()

        hcounter = Signal(hbits)
        vcounter = Signal(vbits)

        self.comb += [
            If(sink.valid,
                active.eq(hactive & vactive),
                source.valid.eq(1),
                If(active,
                    source.de.eq(1),
                )
            ),
            sink.ready.eq(source.ready & source.last)
        ]

        self.sync += \
            If(sink.valid & source.ready,
                source.last.eq(0),
                hcounter.eq(hcounter + 1),

                If(hcounter == 0, hactive.eq(1)),
                If(hcounter == sink.hres, hactive.eq(0)),
                If(hcounter == sink.hsync_start, source.hsync.eq(1)),
                If(hcounter == sink.hsync_end, source.hsync.eq(0)),
                If(hcounter == sink.hscan,
                    hcounter.eq(0),
                    If(vcounter == sink.vscan,
                        vcounter.eq(0),
                        source.last.eq(1)
                    ).Else(
                        vcounter.eq(vcounter + 1)
                    )
                ),

                If(vcounter == 0, vactive.eq(1)),
                If(vcounter == sink.vres, vactive.eq(0)),
                If(vcounter == sink.vsync_start, source.vsync.eq(1)),
                If(vcounter == sink.vsync_end, source.vsync.eq(0))
            )


modes_dw = {
    "rgb":      24,
    "ycbcr422": 16
}


class VideoOutCore(Module, AutoCSR):
    """Video out core

    Generates a video stream from memory.
    """
    def __init__(self, dram_port, mode="rgb", fifo_depth=512):
        try:
            dw = modes_dw[mode]
        except:
            raise ValueError("Unsupported {} video mode".format(mode))
        assert dram_port.dw >= dw
        assert dram_port.dw == 2**log2_int(dw, need_pow2=False)
        self.source = source = stream.Endpoint(video_out_layout(dw))

        # # #

        cd = dram_port.cd

        self.submodules.initiator = initiator = Initiator(cd)
        self.submodules.timing = timing = ClockDomainsRenamer(cd)(TimingGenerator())
        self.submodules.dma = dma = ClockDomainsRenamer(cd)(DMAReader(dram_port, fifo_depth))

        # ctrl path
        self.comb += [
            # dispatch initiator parameters to timing & dma
            timing.sink.valid.eq(initiator.source.valid),
            dma.sink.valid.eq(initiator.source.valid),
            initiator.source.ready.eq(timing.sink.ready),

            # combine timing and dma
            source.valid.eq(timing.source.valid & (~timing.source.de | dma.source.valid)),
            # flush dma/timing when disabled
            If(~initiator.source.valid,
                timing.source.ready.eq(1),
                dma.source.ready.eq(1)
            ).Elif(source.valid & source.ready,
                timing.source.ready.eq(1),
                dma.source.ready.eq(timing.source.de)
            )
        ]

        # data path
        self.comb += [
            # dispatch initiator parameters to timing & dma
            initiator.source.connect(timing.sink, keep=list_signals(frame_parameter_layout)),
            initiator.source.connect(dma.sink, keep=list_signals(frame_dma_layout)),

            # combine timing and dma
            source.de.eq(timing.source.de),
            source.hsync.eq(timing.source.hsync),
            source.vsync.eq(timing.source.vsync),
            source.data.eq(dma.source.data)
        ]
