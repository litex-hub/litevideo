from migen import *

from litex.soc.interconnect import stream

def in_layout(dw):
    return [("in1", dw), ("in2", dw)]

def out_layout(dw):
    return [("out", dw)]


class LeadOne(Module):
    """
    This return the position of leading one of the Signal Object datai, as the
    leadone Signal object. Function input dw defines the data width of datai
    Signal object.
    """
    def __init__(self, dw):
        self.datai = Signal(dw)
        self.leadone = Signal(max=dw)
        for j in range(dw):
            self.comb += If(self.datai[j], self.leadone.eq(dw - j - 1))
