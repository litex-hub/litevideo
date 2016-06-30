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

phy_cls = {
    "xc6" : S6HDMIOutPHY,
    "xc7" : S7HDMIOutPHY
}


class Driver(Module, AutoCSR):
    """Driver

    Low level video interface module.
    """
    def __init__(self, device, pads, external_clocking=None):
        self.sink = sink = stream.Endpoint(phy_layout())

        # # #

        family = device[:3]

        # clocking
        self.submodules.clocking = clocking_cls[family](pads, external_clocking)

        # phy
        self.submodules.hdmi_phy = phy_cls[family](pads)
        if hasattr(self.hdmi_phy, "serdesstrobe"):
            self.comb += self.hdmi_phy.serdesstrobe.eq(self.clocking.serdesstrobe)
        self.comb += sink.connect(self.hdmi_phy.sink)
