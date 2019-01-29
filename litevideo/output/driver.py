from migen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litevideo.output.common import *
from litevideo.output.hdmi.s6 import S6HDMIOutClocking, S6HDMIOutPHY
from litevideo.output.hdmi.s7 import S7HDMIOutClocking, S7HDMIOutPHY


clocking_cls = {
    "xc6" : S6HDMIOutClocking,
    "xc7" : S7HDMIOutClocking,
}

hdmi_phy_cls = {
    "xc6" : S6HDMIOutPHY,
    "xc7" : S7HDMIOutPHY
}

class VGAPHY(Module):
    def __init__(self, pads, mode):
        assert mode != "raw"
        self.sink = stream.Endpoint(phy_layout(mode))

        # # #

        self.comb += [
            self.sink.ready.eq(1),
            pads.hsync_n.eq(~self.sink.hsync),
            pads.vsync_n.eq(~self.sink.vsync),
            pads.r.eq(self.sink.r[8-len(pads.r):]),
            pads.g.eq(self.sink.g[8-len(pads.g):]),
            pads.b.eq(self.sink.b[8-len(pads.b):]),
            pads.psave_n.eq(1)
        ]


class Driver(Module, AutoCSR):
    """Driver

    Low level video interface module.
    """
    def __init__(self, device, pads, mode, external_clocking=None):
        self.sink = sink = stream.Endpoint(phy_layout(mode))

        # # #

        family = device[:3]

        # clocking
        self.submodules.clocking = clocking_cls[family](pads, external_clocking)

        # phy
        vga = hasattr(pads, "hsync_n")
        if vga:
            self.submodules.vga_phy = VGAPHY(pads, mode)
            self.comb += sink.connect(self.vga_phy.sink)
        else:
            self.submodules.hdmi_phy = hdmi_phy_cls[family](pads, mode)
            if hasattr(self.hdmi_phy, "serdesstrobe"):
                self.comb += self.hdmi_phy.serdesstrobe.eq(self.clocking.serdesstrobe)
            self.comb += sink.connect(self.hdmi_phy.sink)
