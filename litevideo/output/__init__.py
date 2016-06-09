from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litevideo.output.core import VideoOutCore
from litevideo.output.driver import Driver

from litevideo.csc.ycbcr2rgb import YCbCr2RGB
from litevideo.csc.ycbcr422to444 import YCbCr422to444


class SyncDelay(Module):
    def __init__(self, latency, de, vsync, hsync):
        self.de = de
        self.vsync = vsync
        self.hsync = hsync
        for i in range(latency):
            next_de = Signal()
            next_vsync = Signal()
            next_hsync = Signal()
            self.sync.pix += [
                next_de.eq(de),
                next_vsync.eq(vsync),
                next_hsync.eq(hsync),
            ]
            self.de = next_de
            self.vsync = next_vsync
            self.hsync = next_hsync


class VideoOut(Module, AutoCSR):
    """Video out

    Generates a video from memory.
    """
    def __init__(self, device, pads, dram_port,  mode="rgb", external_clocking=None):
        cd = dram_port.cd

        self.submodules.core = core = VideoOutCore(dram_port, mode)
        self.submodules.fifo = fifo = ClockDomainsRenamer(cd)(stream.SyncFIFO(self.core.source.description, 512))
        self.submodules.driver = driver = Driver(device, pads, external_clocking)
        self.comb += core.source.connect(fifo.sink)

        if mode == "rgb":
            self.comb += [
                fifo.source.connect(driver.sink, omit=["data"]),
                driver.sink.r.eq(fifo.source.data[:8]),
                driver.sink.g.eq(fifo.source.data[8:16]),
                driver.sink.b.eq(fifo.source.data[16:])
            ]

        elif mode == "ycbcr444":
            ycbcr2rgb = ClockDomainsRenamer(cd)(YCbCr2RGB())
            sync_delay = SyncDelay(ycbcr2rgb.latency,
                                   fifo.source.de,
                                   fifo.source.vsync,
                                   fifo.source.hsync)
            self.submodules += ycbcr2rgb, sync_delay
            self.comb += [
                ycbcr2rgb.sink.valid.eq(fifo.source.valid),
                ycbcr2rgb.sink.y.eq(fifo.source.data[:8]),
                ycbcr2rgb.sink.cb.eq(fifo.source.data[8:16]),
                ycbcr2rgb.sink.cr.eq(fifo.source.data[16:])
            ]
            self.comb += [
                ycbcr2rgb.source.connect(driver.sink),
                driver.sink.de.eq(sync_delay.de),
                driver.sink.vsync.eq(sync_delay.vsync),
                driver.sink.hsync.eq(sync_dela)
            ]
        elif mode == "ycbcr422":
            ycbcr422to444 = ClockDomainsRenamer(cd)(YCbCr422to444())
            ycbcr2rgb = ClockDomainsRenamer(cd)(YCbCr2RGB())
            sync_delay = SyncDelay(ycbcr2rgb.latency + ycbcr422to444.latency,
                                   fifo.source.de,
                                   fifo.source.vsync,
                                   fifo.source.hsync)
            self.submodules += ycbcr422to444, ycbcr2rgb, sync_delay
            self.comb += [
                ycbcr422to444.sink.valid.eq(fifo.source.valid),
                ycbcr422to444.sink.y.eq(fifo.source.data[:8]),
                ycbcr422to444.sink.cb_cr.eq(fifo.source.data[8:16]),
                ycbcr422to444.source.connect(ycbcr2rgb.sink)
            ]
            self.comb += [
                ycbcr2rgb.source.connect(driver.sink),
                driver.sink.de.eq(sync_delay.de),
                driver.sink.vsync.eq(sync_delay.vsync),
                driver.sink.hsync.eq(sync_dela)
            ]
        else:
            raise ValueError("Video mode {} not supported".format(mode))
