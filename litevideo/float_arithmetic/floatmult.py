'''
FloatMultDatapath class: Multiply two floating point numbers a and b, returns
their output c in the same float16 format.

FloatMult class: Use the FloatMultDatapath above and generates a modules
implemented using five stage pipeline.
'''

from migen import *

from litex.soc.interconnect.stream import *
from litex.soc.interconnect.csr import *

from litevideo.float_arithmetic.common import *


@CEInserter()
class FloatMultDatapath(Module):
    """
    This adds a floating point multiplication unit.
    Inputs: in1 and in2
    Output: out
    Implemented as a 5 stage pipeline, design is based on float16 design doc.
    Google Docs Link: https://goo.gl/Rvx2B7
    """
    latency = 5
    def __init__(self, dw):
        self.sink = sink = Record(in_layout(dw))
        self.source = source = Record(out_layout(dw))

        # delay input a/b signals
        in_delayed = [sink]
        for i in range(self.latency):
            in_n = Record(in_layout(dw))
            for name in ["in1", "in2"]:
                self.sync += getattr(in_n, name).eq(getattr(in_delayed[-1], name))
            in_delayed.append(in_n)

        # stage 1
        # Unpack
        # Look for special cases

        in1_frac = Signal(10)
        in2_frac = Signal(10)
        in1_mant = Signal(11)
        in2_mant = Signal(11)

        in1_exp = Signal(5)
        in2_exp = Signal(5)
        in1_exp1 = Signal(5)
        in2_exp1 = Signal(5)

        in1_sign = Signal()
        in2_sign = Signal()

        out_status1 = Signal(2)
        # 00-0 Zero
        # 01-1 Inf
        # 10-2 Nan
        # 11-3 Normal

        self.comb += [
            in1_frac.eq(sink.in1[:10]),
            in2_frac.eq(sink.in2[:10]),

            in1_exp.eq(sink.in1[10:15]),
            in2_exp.eq(sink.in2[10:15]),

            in1_sign.eq(sink.in1[15]),
            in2_sign.eq(sink.in2[15])
        ]

        self.sync += [
            If(in1_exp == 0,
                in1_mant.eq(Cat(in1_frac, 0)),
                in1_exp1.eq(in1_exp + 1)
            ).Else(
                in1_mant.eq(Cat(in1_frac, 1)),
                in1_exp1.eq(in1_exp)
            ),

            If(in2_exp == 0,
                in2_mant.eq(Cat(in2_frac, 0)),
                in2_exp1.eq(in2_exp + 1)
            ).Else(
                in2_mant.eq(Cat(in2_frac, 1)),
                in2_exp1.eq(in2_exp)
            ),

            If(((in1_exp == 0) & (in1_frac == 0)),
                out_status1.eq(0)
            ).Elif(((in2_exp == 0) & (in2_frac == 0)),
                out_status1.eq(0)
            ).Else(
                out_status1.eq(3)
            )
        ]

        # stage 2
        # Multiply fractions and add exponents
        out_mult = Signal(22)
        out_exp = Signal((7, True))
        out_status2 = Signal(2)

        self.sync += [
            out_mult.eq(in1_mant * in2_mant),
            out_exp.eq(in1_exp1 + in2_exp1 - 15),
            out_status2.eq(out_status1),
        ]

        # stage 3
        # Leading one detector
        one_ptr = Signal(5)
        out_status3 = Signal(2)
        out_mult3 = Signal(22)
        out_exp3 = Signal((7, True))

        lead_one_ptr = Signal(5)
        self.submodules.leadone = LeadOne(22)
        self.comb += [
            self.leadone.datai.eq(out_mult),
            lead_one_ptr.eq(self.leadone.leadone)
        ]

        self.sync += [
            out_status3.eq(out_status2),
            out_mult3.eq(out_mult),
            out_exp3.eq(out_exp),
            one_ptr.eq(lead_one_ptr)
        ]

        # stage 4
        # Shift and Adjust
        out_exp_adjust = Signal((7, True))
        out_mult_shift = Signal(22)
        out_status4 = Signal(2)

        self.sync += [
            out_status4.eq(out_status3),
            If((out_exp3 - one_ptr) < 1,
                out_exp_adjust.eq(0),
                out_mult_shift.eq(((out_mult >> (0 - out_exp3)) << 1))
            ).Else(
                out_exp_adjust.eq(out_exp3 + 1 - one_ptr),
                out_mult_shift.eq(out_mult << one_ptr + 1)
            )
        ]

        # stage 5
        # Normalize and pack
        self.sync += [
            If(out_status4 == 0,
                source.out.eq(0)
            ).Elif(out_status4 == 3,
                source.out.eq(Cat(out_mult_shift[12:], out_exp_adjust[:5],0))
            )
        ]

class FloatMult(PipelinedActor, Module, AutoCSR):
    def __init__(self, dw=16):
        self.sink = sink = stream.Endpoint(EndpointDescription(in_layout(dw)))
        self.source = source = stream.Endpoint(EndpointDescription(out_layout(dw)))

        # # #

        self.submodules.datapath = FloatMultDatapath(dw)
        PipelinedActor.__init__(self, self.datapath.latency)
        self.comb += self.datapath.ce.eq(self.pipe_ce)
        for name in ["in1", "in2"]:
            self.comb += getattr(self.datapath.sink, name).eq(getattr(sink, name))
        self.comb += getattr(source, "out").eq(getattr(self.datapath.source, "out"))

        # Comment this out when simulating (why?)

#        self._float_in1 = CSRStorage(dw)
#        self._float_in2 = CSRStorage(dw)
#        self._float_out = CSRStatus(dw)

#        self.comb += [
#            getattr(sink, "in1").eq(self._float_in1.storage),
#            getattr(sink, "in2").eq(self._float_in2.storage),
#            self._float_out.status.eq(getattr(source, "out"))
#        ]
