from litex.gen import *

from litex.soc.interconnect import stream


def saturate(i, o, minimum, maximum):
    return [
        If(i > maximum,
            o.eq(maximum)
        ).Elif(i < minimum,
            o.eq(minimum)
        ).Else(
            o.eq(i)
        )
    ]

def in_layout(dw):
    return [("a", dw), ("b", dw)]

def out_layout(dw):
    return [("c", dw)]
