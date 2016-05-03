from litex.gen import *

from litex.soc.interconnect.stream import *

from litedram.common import LiteDRAMPort

from litevideo.output.core import VideoOutCore


class TB(Module):
    def __init__(self):
        self.dram_port = LiteDRAMPort(aw=32, dw=32)
        self.submodules.core = VideoOutCore(self.dram_port)
        self.comb += self.core.source.ready.eq(1)


class DRAMMemory:
    def __init__(self, width, depth, init=[]):
        self.width = width
        self.depth = depth
        self.mem = []
        for d in init:
            self.mem.append(d)
        for _ in range(depth-len(init)):
            self.mem.append(0)

    @passive
    def read_generator(self, dram_port):
        address = 0
        pending = 0
        while True:
            yield dram_port.ready.eq(0)
            yield dram_port.rdata_valid.eq(0)
            if pending:
                yield dram_port.rdata_valid.eq(1)
                yield dram_port.rdata.eq(self.mem[address%self.depth])
                yield
                yield dram_port.rdata_valid.eq(0)
                yield dram_port.rdata.eq(0)
                pending = 0
            elif (yield dram_port.valid):
                pending = not (yield dram_port.we)
                address = (yield dram_port.adr)
                yield
                yield dram_port.ready.eq(1)
            yield


def main_generator(dut):
    for i in range(100):
        yield
    yield dut.core.initiator.hres.storage.eq(16)
    yield dut.core.initiator.hsync_start.storage.eq(18)
    yield dut.core.initiator.hsync_end.storage.eq(20)
    yield dut.core.initiator.hscan.storage.eq(24)

    yield dut.core.initiator.vres.storage.eq(32)
    yield dut.core.initiator.vsync_start.storage.eq(34)
    yield dut.core.initiator.vsync_end.storage.eq(36)
    yield dut.core.initiator.vscan.storage.eq(48)
    
    yield dut.core.initiator.base.storage.eq(0)
    yield dut.core.initiator.end.storage.eq(16*32)
    
    yield
    yield dut.core.initiator.enable.storage.eq(1)
    yield
    for i in range(4096):
        yield


if __name__ == "__main__":
    tb = TB()
    mem = DRAMMemory(32, 1024, [i for i in range(1024)])
    generators = {
        "sys" :   [main_generator(tb),
                   mem.read_generator(tb.dram_port)]
    }
    clocks = {"sys": 10}
    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
