from litex.gen import *

from litex.soc.interconnect import stream

def in_layout(dw):
    return [("in1", dw), ("in2", dw)]

def out_layout(dw):
    return [("out", dw)]
