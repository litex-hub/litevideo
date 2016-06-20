from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litedram.frontend.dma import LiteDRAMDMAReader

from litevideo.output.common import *
from litevideo.output.hdmi.s6 import S6HDMIOutClocking, S6HDMIOutPHY
from litevideo.output.hdmi.s7 import S7HDMIOutClocking, S7HDMIOutPHY


class Initiator(Module, AutoCSR):
    """Initiator

    Generates the H/V and dma parameters of a frame.
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
        self.sync += [
            If(self.enable.storage,
                cdc.sink.valid.eq(1)
            ).Elif(self.source.ready,
                cdc.sink.valid.eq(0)
            )
        ]

        self.comb += cdc.source.connect(self.source)


class DMAReader(Module, AutoCSR):
    """DMA reader

    Generates the data stream of a frame.
    """
    def __init__(self, dram_port, fifo_depth=512):
        self.sink = sink = stream.Endpoint(frame_dma_layout)
        self.source = source = stream.Endpoint([("data", dram_port.dw)])

        # # #

        self.submodules.reader = LiteDRAMDMAReader(dram_port, fifo_depth)
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        shift = log2_int(dram_port.dw//8)
        base = self.sink.base[shift:shift+dram_port.aw]
        length = self.sink.length[shift:shift+dram_port.aw]

        address = Signal(dram_port.aw)
        address_init = Signal()
        address_inc = Signal()
        self.sync += \
            If(address_init,
                address.eq(base)
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
                If(address == (base + length - 1),
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

modes_dw = {
    "rgb": 24,
    "ycbcr422": 16
}


class VideoOutCore(Module, AutoCSR):
    """Video out core

    Generates a video stream from memory.
    """
    def __init__(self, dram_port, mode="rgb"):
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
        self.submodules.dma = dma = ClockDomainsRenamer(cd)(DMAReader(dram_port))

        # ctrl path
        timing_done = Signal()
        dma_done = Signal()
        cd_sync = getattr(self.sync, cd)
        cd_sync += [
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
            timing.sink.valid.eq(initiator.source.valid),
            dma.sink.valid.eq(initiator.source.valid),
            initiator.source.ready.eq((timing.sink.ready | timing_done) &
                                      (dma.sink.ready | dma_done)),

            # combine timing and dma
            source.valid.eq(timing.source.valid & (~timing.source.de | dma.source.valid)),
            timing.source.ready.eq(source.valid & source.ready),
            dma.source.ready.eq(timing.source.de & source.valid & source.ready)
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
