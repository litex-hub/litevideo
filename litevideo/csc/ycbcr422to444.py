# ycbcr422to444

from migen import *

from litex.soc.interconnect.stream import *

from litevideo.csc.common import *

@ResetInserter()
class YCbCr422to444(Module):
    """YCbCr 422 to 444

      Input:                    Output:
        Y0    Y1    Y2   Y3       Y0     Y1   Y2   Y3
      Cb01  Cr01  Cb23 Cr23  --> Cb01  Cb01 Cb23 Cb23
                                 Cr01  Cr01 Cr23 Cr23
    """
    latency = 2
    def __init__(self, dw=8):
        self.sink = sink = stream.Endpoint(EndpointDescription(ycbcr422_layout(dw)))
        self.source = source = stream.Endpoint(EndpointDescription(ycbcr444_layout(dw)))

        # # #

        y_fifo = stream.SyncFIFO([("data", dw)], 4)
        cb_fifo = stream.SyncFIFO([("data", dw)], 4)
        cr_fifo = stream.SyncFIFO([("data", dw)], 4)
        self.submodules += y_fifo, cb_fifo, cr_fifo

        # input
        parity_in = Signal()
        self.sync += If(sink.valid & sink.ready, parity_in.eq(~parity_in))
        self.comb += [
            If(~parity_in,
                y_fifo.sink.valid.eq(sink.valid & sink.ready),
                y_fifo.sink.data.eq(sink.y),
                cb_fifo.sink.valid.eq(sink.valid & sink.ready),
                cb_fifo.sink.data.eq(sink.cb_cr),
                sink.ready.eq(y_fifo.sink.ready & cb_fifo.sink.ready)
            ).Else(
                y_fifo.sink.valid.eq(sink.valid & sink.ready),
                y_fifo.sink.data.eq(sink.y),
                cr_fifo.sink.valid.eq(sink.valid & sink.ready),
                cr_fifo.sink.data.eq(sink.cb_cr),
                sink.ready.eq(y_fifo.sink.ready & cr_fifo.sink.ready)
            )
        ]


        # output
        parity_out = Signal()
        self.sync += If(source.valid & source.ready, parity_out.eq(~parity_out))
        self.comb += [
            source.valid.eq(y_fifo.source.valid &
                            cb_fifo.source.valid &
                            cr_fifo.source.valid),
            source.y.eq(y_fifo.source.data),
            source.cb.eq(cb_fifo.source.data),
            source.cr.eq(cr_fifo.source.data),
            y_fifo.source.ready.eq(source.valid & source.ready),
            cb_fifo.source.ready.eq(source.valid & source.ready & parity_out),
            cr_fifo.source.ready.eq(source.valid & source.ready & parity_out)
        ]
