from litex.gen import *
from litex.soc.interconnect.stream import *

from litevideo.csc.common import *
from litevideo.csc.ycbcr422to444 import YCbCr422to444


class TB(Module):
    def __init__(self):
        self.submodules.ycbcr422to444 = YCbCr422to444()


def main_generator(dut):
    yield dut.ycbcr422to444.source.ready.eq(1)
    for i in range(16):
        yield
    for i in range(8):
        yield dut.ycbcr422to444.sink.valid.eq(1)
        yield dut.ycbcr422to444.datapath.first.eq(1)
        yield dut.ycbcr422to444.sink.y.eq(0x1)
        yield dut.ycbcr422to444.sink.cb_cr.eq(0x11)
        yield
        yield dut.ycbcr422to444.sink.valid.eq(1)
        yield dut.ycbcr422to444.datapath.first.eq(0)
        yield dut.ycbcr422to444.sink.y.eq(0x2)
        yield dut.ycbcr422to444.sink.cb_cr.eq(0x12)
        yield
        yield dut.ycbcr422to444.sink.valid.eq(0)
        for j in range(i):
            yield

if __name__ == "__main__":
    tb = TB()
    generators = {"sys" :   [main_generator(tb)]}
    clocks = {"sys": 10}
    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
