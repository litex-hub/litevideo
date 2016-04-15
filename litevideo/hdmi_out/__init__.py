from litex.gen import *

from litex.soc.interconnect.csr import AutoCSR

from litevideo.hdmi_out.core import HDMIOutCore
from litevideo.hdmi_out.phy import HDMIOutPHY

class HDMIOut(Module, AutoCSR):
    def __init__(self, device, pads, lasmim, external_clocking=None):
        self.submodules.core = HDMIOutCore(lasmim)
        self.submodules.phy = HDMIOutPHY(device,
                                      self.core.pack_factor,
                                      pads,
                                      external_clocking)
        self.comb += self.core.source.connect(self.phy.sink)
