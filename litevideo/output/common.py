from litex.gen import *

from litex.soc.interconnect import stream

hbits = 12
vbits = 12

bpp = 16
bpc = 8
pixel_layout_s = [
    ("cb_cr", bpc),
    ("y", bpc)
]

def pixel_layout(pack_factor):
    return [("p"+str(i), pixel_layout_s) for i in range(pack_factor)]

frame_parameter_layout = [
    ("hres", hbits),
    ("hsync_start", hbits),
    ("hsync_end", hbits),
    ("hscan", hbits),
    ("vres", vbits),
    ("vsync_start", vbits),
    ("vsync_end", vbits),
    ("vscan", vbits)
]

frame_dma_layout = [
    ("base", 32),
    ("end",  32)
]

frame_timing_layout = [
    ("hsync", 1),
    ("vsync", 1),
    ("de", 1)
]

color_bar_parameter_layout = [("hres", hbits)]

def video_out_layout(dw):
    param_layout = frame_timing_layout
    payload_layout = [("data", dw)]
    return stream.EndpointDescription(payload_layout, param_layout)

def list_signals(layout):
    return [f[0] for f in layout]

phy_layout = frame_timing_layout + [("r", 8), ("g", 8), ("b", 8)]
