from migen import *

from litex.soc.interconnect import stream

hbits = 12
vbits = 12

def list_signals(layout):
    return [f[0] for f in layout]

frame_parameter_layout = [
    ("hres",        hbits),
    ("hsync_start", hbits),
    ("hsync_end",   hbits),
    ("hscan",       hbits),
    ("vres",        vbits),
    ("vsync_start", vbits),
    ("vsync_end",   vbits),
    ("vscan",       vbits)
]

frame_dma_layout = [
    ("base",   32),
    ("length", 32),
]

frame_timing_layout = [
    ("hsync", 1),
    ("vsync", 1),
    ("de",    1)
]

color_bar_parameter_layout = [("hres", hbits)]

def video_out_layout(dw):
    param_layout = frame_timing_layout
    payload_layout = [("data", dw)]
    return stream.EndpointDescription(payload_layout, param_layout)

def phy_layout(mode):
    if mode == "raw":
        param_layout = frame_timing_layout # not used
        payload_layout = [("c0", 10), ("c1", 10), ("c2", 11)]
        return stream.EndpointDescription(payload_layout, param_layout)
    else:
        param_layout = frame_timing_layout
        payload_layout = [("r", 8), ("g", 8), ("b", 8)]
        return stream.EndpointDescription(payload_layout, param_layout)
