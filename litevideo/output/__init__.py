from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litevideo.output.core import VideoOutCore
from litevideo.output.driver import Driver


class VideoOut(Module, AutoCSR):
    """Video out

    Generates a video from memory.
    """
    def __init__(self, device, pads, lasmim, external_clocking=None):
        self.submodules.core = VideoOutCore(lasmim)
        self.submodules.driver = Driver(device,
                                        self.core.pack_factor,
                                        pads,
                                        external_clocking)
        self.comb += self.core.source.connect(self.driver.sink)

