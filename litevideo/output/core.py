from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *
from litex.soc.interconnect import dma_lasmi

from litevideo.output.common import *
from litevideo.output.hdmi.s6 import S6HDMIOutClocking, S6HDMIOutPHY
from litevideo.output.hdmi.s7 import S7HDMIOutClocking, S7HDMIOutPHY


class Initiator(Module, AutoCSR):
    """Initiator

    Generates the H/V and dma parameters of a frame.
    """
    def __init__(self):
        self.source = stream.Endpoint(frame_parameter_layout +
                                      frame_dma_layout)

        # # #

        self.enable = CSRStorage()
        for name, width in frame_parameter_layout + frame_dma_layout:
            setattr(self, name, CSRStorage(width, name=name))
            self.comb += getattr(self.source, name).eq(getattr(self, name).storage)
        self.sync += [
            If(self.enable.storage,
                self.source.valid.eq(1)
            ).Elif(self.source.ready,
                self.source.valid.eq(0)
            )
        ]


class DMAReader(Module, AutoCSR):
    """DMA reader

    Generates the data stream of a frame.
    """
    def __init__(self, lasmim):
        self.sink = sink = stream.Endpoint(frame_dma_layout)
        self.source = source = stream.Endpoint([("data", lasmim.dw)])

        # # #

        self.submodules.reader = dma_lasmi.Reader(lasmim)
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        address = Signal(lasmim.aw)
        address_init = Signal()
        address_inc = Signal()
        self.sync += \
            If(address_init,
                address.eq(self.sink.base)
            ).Elif(address_inc,
                address.eq(address + 1)
            )

        fsm.act("IDLE",
            address_init.eq(1),
            If(sink.valid,
                NextState("READ")
            )
        )
        fsm.act("READ",
            self.reader.sink.valid.eq(1),
            If(self.reader.sink.ready,
                address_inc.eq(1),
                If(address == self.sink.end,
                    self.sink.ready.eq(1),
                    NextState("IDLE")
                )
            )
        )
        self.comb += [
            self.reader.sink.address.eq(address),
            self.reader.source.connect(self.source)
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


class VideoOutCore(Module, AutoCSR):
    """Video out core

    Generates a video stream from memory.
    """
    def __init__(self, lasmim):
        self.source = source = stream.Endpoint(video_out_layout(lasmim.dw))

        # # #

        self.submodules.initiator = initiator = Initiator()
        self.submodules.timing = timing = TimingGenerator()
        self.submodules.dma = dma = DMAReader(lasmim)

        # ctrl path
        timing_done = Signal()
        dma_done = Signal()
        self.sync += [
            If(initiator.source.ready,
                timing_done.eq(0)
            ).Elif(timing.sink.ready,
                timing_done.eq(1)
            ),
            If(initiator.source.ready,
                dma_done.eq(0)
            ).Elif(dma.sink.ready,
                dma_done.eq(1)
            )
        ]
        self.comb += [
            # dispatch initiator parameters to timing & dma
            timing.sink.valid.eq(initiator.source.valid & ~timing_done),
            dma.sink.valid.eq(initiator.source.valid & ~dma_done),
            initiator.source.ready.eq((timing.sink.ready | timing_done) &
                                      (dma.sink.ready | dma_done)),

            # combine timing and dma
            source.valid.eq(timing.source.valid & (-timing.source.de | dma.source.valid)),
            timing.source.ready.eq(source.valid & source.ready),
            dma.source.ready.eq(-timing.source.de & source.valid & source.ready)
        ]

        # data path
        self.comb += [
            # dispatch initiator parameters to timing & dma
            initiator.source.connect(timing.sink, keep=list_signals(frame_parameter_layout)),
            initiator.source.connect(dma.sink, keep=list_signals(frame_dma_layout)),

            # combine timing and dma
        	timing.source.connect(source, keep=list_signals(frame_dma_layout)),
            dma.source.connect(source, keep=["data"]),
        ]
