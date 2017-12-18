from litex.gen import *
from litex.soc.interconnect.csr import AutoCSR

from litevideo.input.edid import EDID, _default_edid
from litevideo.input.clocking import S6Clocking, S7Clocking
from litevideo.input.datacapture import S6DataCapture, S7DataCapture
from litevideo.input.charsync import CharSync
from litevideo.input.wer import WER
from litevideo.input.decoding import Decoding
from litevideo.input.chansync import ChanSync
from litevideo.input.analysis import SyncPolarity, ResolutionDetection
from litevideo.input.analysis import FrameExtraction
from litevideo.input.dma import DMA


clocking_cls = {
    "xc6" : S6Clocking,
    "xc7" : S7Clocking,
}

datacapture_cls = {
    "xc6" : S6DataCapture,
    "xc7" : S7DataCapture
}


class HDMIIn(Module, AutoCSR):
    def __init__(self, pads, dram_port=None, n_dma_slots=2, fifo_depth=512, device="xc6",
        default_edid=_default_edid, polarities=[0, 0, 0], clkin_freq=148.5e6):
        if hasattr(pads, "scl"):
            self.submodules.edid = EDID(pads, default_edid)
        self.submodules.clocking = clocking_cls[device](pads, clkin_freq)

        for datan in range(3):
            name = "data" + str(datan)

            cap = datacapture_cls[device](getattr(pads, name + "_p"),
                                          getattr(pads, name + "_n"),
                                          polarity=polarities[datan])
            setattr(self.submodules, name + "_cap", cap)
            if hasattr(cap, "serdesstrobe"):
                self.comb += cap.serdesstrobe.eq(self.clocking.serdesstrobe)

            charsync = CharSync()
            setattr(self.submodules, name + "_charsync", charsync)
            self.comb += charsync.raw_data.eq(cap.d)

            wer = WER()
            setattr(self.submodules, name + "_wer", wer)
            self.comb += wer.data.eq(charsync.data)

            decoding = Decoding()
            setattr(self.submodules, name + "_decod", decoding)
            self.comb += [
                decoding.valid_i.eq(charsync.synced),
                decoding.input.eq(charsync.data)
            ]

        self.submodules.chansync = ChanSync()
        self.comb += [
            self.chansync.valid_i.eq(self.data0_decod.valid_o &
                                     self.data1_decod.valid_o &
                                     self.data2_decod.valid_o),
            self.chansync.data_in0.eq(self.data0_decod.output),
            self.chansync.data_in1.eq(self.data1_decod.output),
            self.chansync.data_in2.eq(self.data2_decod.output)
        ]

        self.submodules.syncpol = SyncPolarity()
        self.comb += [
            self.syncpol.valid_i.eq(self.chansync.chan_synced),
            self.syncpol.data_in0.eq(self.chansync.data_out0),
            self.syncpol.data_in1.eq(self.chansync.data_out1),
            self.syncpol.data_in2.eq(self.chansync.data_out2)
        ]

        self.submodules.resdetection = ResolutionDetection()
        self.comb += [
            self.resdetection.valid_i.eq(self.syncpol.valid_o),
            self.resdetection.de.eq(self.syncpol.de),
            self.resdetection.vsync.eq(self.syncpol.vsync)
        ]

        if dram_port is not None:
            self.submodules.frame = FrameExtraction(dram_port.dw, fifo_depth)
            self.comb += [
                self.frame.valid_i.eq(self.syncpol.valid_o),
                self.frame.de.eq(self.syncpol.de),
                self.frame.vsync.eq(self.syncpol.vsync),
                self.frame.r.eq(self.syncpol.r),
                self.frame.g.eq(self.syncpol.g),
                self.frame.b.eq(self.syncpol.b)
            ]


            self.submodules.dma = DMA(dram_port, n_dma_slots)
            self.comb += self.frame.frame.connect(self.dma.frame)
            self.ev = self.dma.ev

    autocsr_exclude = {"ev"}
