from litex.gen import *

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
    def __init__(self, mode):
        assert mode != "raw"
        self.sink = stream.Endpoint(phy_layout(mode))

        # # #

        self.comb += [
            pads_vga.hsync_n.eq(~self.sink.hsync),
            pads_vga.vsync_n.eq(~self.sink.vsync),
            pads_vga.r.eq(self.sink.r),
            pads_vga.g.eq(self.sink.g),
            pads_vga.b.eq(self.sink.b),
            pads_vga.psave_n.eq(1)
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
        vga = hasattr("pads", "hsync_n")
        if vga:
            self.submodules.vga_phy = VGA(pads, mode)
            self.comb += sink.connect(self.hdmi_phy.sink)
        else:
            self.submodules.hdmi_phy = hdmiphy_cls[family](pads, mode)
            if hasattr(self.hdmi_phy, "serdesstrobe"):
                self.comb += self.hdmi_phy.serdesstrobe.eq(self.clocking.serdesstrobe)
                self.comb += sink.connect(self.hdmi_phy.sink)
