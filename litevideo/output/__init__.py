from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litevideo.output.common import *
from litevideo.output.core import VideoOutCore
from litevideo.output.driver import Driver

from litevideo.csc.ycbcr2rgb import YCbCr2RGB
from litevideo.csc.ycbcr422to444 import YCbCr422to444


class TimingDelay(Module):
    def __init__(self, latency):
        self.sink = stream.Endpoint(frame_timing_layout)
        self.source = stream.Endpoint(frame_timing_layout)

        # # #

        for name in list_signals(frame_timing_layout):
            s = getattr(self.sink, name)
            for i in range(latency):
                next_s = Signal()
                self.sync += next_s.eq(s)
                s = next_s
            self.comb += getattr(self.source, name).eq(s)


class VideoOut(Module, AutoCSR):
    """Video out

    Generates a video from memory.
    """
    def __init__(self, device, pads, dram_port,  mode="rgb", external_clocking=None):
        cd = dram_port.cd

        self.submodules.core = core = VideoOutCore(dram_port, mode)
        self.submodules.driver = driver = Driver(device, pads, external_clocking)

        if mode == "rgb":
            self.comb += [
                core.source.connect(driver.sink, omit=["data"]),
                driver.sink.r.eq(core.source.data[:8]),
                driver.sink.g.eq(core.source.data[8:16]),
                driver.sink.b.eq(core.source.data[16:])
            ]
        elif mode == "ycbcr422":
            ycbcr422to444 = ClockDomainsRenamer(cd)(YCbCr422to444())
            ycbcr2rgb = ClockDomainsRenamer(cd)(YCbCr2RGB())
            timing_delay = TimingDelay(ycbcr422to444.latency + ycbcr2rgb.latency)
            timing_delay = ClockDomainsRenamer(cd)(timing_delay)
            self.submodules += ycbcr422to444, ycbcr2rgb, timing_delay

            # data / control
            de_r = Signal()
            sync_cd = getattr(self.sync, cd)
            sync_cd += de_r.eq(core.source.de)
            self.comb += [
                ycbcr422to444.sink.valid.eq(core.source.valid),
                ycbcr422to444.sink.y.eq(core.source.data[:8]),
                ycbcr422to444.sink.cb_cr.eq(core.source.data[8:]),
                ycbcr422to444.datapath.first.eq(core.source.de & ~de_r),
                core.source.ready.eq(ycbcr422to444.sink.ready),

                ycbcr422to444.source.connect(ycbcr2rgb.sink),

                ycbcr2rgb.source.connect(driver.sink)
            ]
            # timing
            self.comb += [
                timing_delay.sink.de.eq(core.source.de),
                timing_delay.sink.vsync.eq(core.source.vsync),
                timing_delay.sink.hsync.eq(core.source.hsync),

                driver.sink.de.eq(timing_delay.source.de),
                driver.sink.vsync.eq(timing_delay.source.vsync),
                driver.sink.hsync.eq(timing_delay.source.hsync)
            ]
        else:
            raise ValueError("Video mode {} not supported".format(mode))
