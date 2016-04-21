from litex.gen import *

from litex.soc.interconnect import stream

from litevideo.output.common import *


class ColorBarPattern(Module):
    """Color Bar Pattern
    """
    def __init__(self):
        self.sink = sink = stream.Endpoint(color_bar_parameter_layout)
        self.source = source = stream.Endpoint([("r", 8), ("g", 8), ("b", 8)])

        # # #

        # ctrl
        pix = Signal(hbits)
        bar = Signal(3)
        self.sync += [
            If(sink.valid,
                source.valid.eq(1),
                If(source.ready,
                    If(pix == (sink.hres[3:]-1),
                        pix.eq(0),
                        bar.eq(bar + 1)
                    ).Else(
                        pix.eq(pix + 1)
                    )
                )
            )
        ]

        # data
        color_bar = [
            # r ,  g ,  b
            [255, 255, 255],
            [255, 255,   0],
            [0,   255, 255],
            [0,   255,   0],
            [255,   0, 255],
            [255,   0,   0],
            [0,     0, 255],
            [0,     0,   0],
        ]
        cases = {}
        for i in range(8):
            cases[i] = [
                source.r.eq(color_bar[i][0]),
                source.g.eq(color_bar[i][1]),
                source.b.eq(color_bar[i][2])
            ]
        self.sync += Case(bar, cases)
