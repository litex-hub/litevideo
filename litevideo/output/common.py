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

frame_synchro_layout = [
    ("hsync", 1),
    ("vsync", 1),
    ("de", 1)
]

def phy_description(pack_factor):
    param_layout = frame_synchro_layout
    payload_layout = [("data", 2*8*pack_factor)]
    return stream.EndpointDescription(payload_layout, param_layout)
