# rgb2rgb16f

from litex.gen import *
from litex.soc.interconnect.stream import *

from litevideo.csc.common import *


class LeadOne(Module):
    def __init__(self):

        self.datai = Signal(8)
        self.leadone = Signal(4)
        for j in range(8):
            self.comb += If(self.datai[j], self.leadone.eq(8 - j-1))

@CEInserter()
class PIX2PIXFDatapath(Module):
    """ 
    Converts a 8 bit unsigned int represented by a pixel in 
    the range [0-255] to a 16 bit half precision floating point 
    pix_number defined in the range [0-1] 
    """
    latency = 2

    def __init__(self, pix_w, pixf_w):
        self.sink = sink = Record(pix_layout(pix_w))
        self.source = source = Record(pixf_layout(pixf_w))

        # # #

        # delay pix signal
        pix_delayed = [sink]
        for i in range(self.latency):
            pix_n = Record(pix_layout(pix_w))
            self.sync += getattr(pix_n, "pix").eq(getattr(pix_delayed[-1], "pix"))
            pix_delayed.append(pix_n)

        # Hardware implementation:

        # Stage 1
        # Leading one detector

        lshift = Signal(4)
        frac_val = Signal(10)

        self.submodules.l1 = LeadOne()
        self.comb += [
            self.l1.datai.eq(sink.pix)
        ]

        self.sync += [

            lshift.eq(self.l1.leadone),
            frac_val[3:].eq(sink.pix[:7]),
            frac_val[:3].eq(0)
        ]

        # Stage 2
        # Adjust frac and exp components as per lshift
        # Pack in 16bit float

        self.sync += [
            source.pixf[:10].eq(frac_val << lshift),
            source.pixf[10:15].eq(15 - 1 - lshift),
            source.pixf[15].eq(1)
        ]
        
class RGB2RGB16f(PipelinedActor, Module):
    def __init__(self, rgb_w=8, rgb16f_w=16):
        self.sink = sink = stream.Endpoint(EndpointDescription(rgb_layout(rgb_w)))
        self.source = source = stream.Endpoint(EndpointDescription(rgb16f_layout(rgb16f_w)))
        # # #

        for name in ["r", "g", "b"]:
            self.submodules.datapath = PIX2PIXFDatapath(rgb_w, rgb16f_w)
            PipelinedActor.__init__(self, self.datapath.latency)
            self.comb += self.datapath.ce.eq(self.pipe_ce)
            self.comb += getattr(self.datapath.sink, "pix").eq(getattr(sink, name))
            self.comb += getattr(source, name + "f").eq(getattr(self.datapath.source, "pixf"))
