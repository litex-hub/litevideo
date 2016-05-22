from litex.gen import *

from litex.soc.interconnect.stream import *

from litedram.common import LiteDRAMPort

from litevideo.output.core import VideoOutCore


class TB(Module):
    def __init__(self):
        self.dram_port = LiteDRAMPort(aw=32, dw=32)
        self.submodules.core = VideoOutCore(self.dram_port)
        self.sync += \
            self.core.source.ready.eq(~self.core.source.ready)


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
            yield dram_port.cmd.ready.eq(0)
            yield dram_port.rdata.valid.eq(0)
            if pending:
                yield dram_port.rdata.valid.eq(1)
                yield dram_port.rdata.data.eq(self.mem[address%self.depth])
                yield
                yield dram_port.rdata.valid.eq(0)
                yield dram_port.rdata.data.eq(0)
                pending = 0
            elif (yield dram_port.cmd.valid):
                pending = not (yield dram_port.cmd.we)
                address = (yield dram_port.cmd.adr)
                yield
                yield dram_port.cmd.ready.eq(1)
            yield


def main_generator(dut):
    for i in range(100):
        yield
    yield dut.core.initiator.hres.storage.eq(16)
    yield dut.core.initiator.hsync_start.storage.eq(18)
    yield dut.core.initiator.hsync_end.storage.eq(20)
    yield dut.core.initiator.hscan.storage.eq(24)

    yield dut.core.initiator.vres.storage.eq(16)
    yield dut.core.initiator.vsync_start.storage.eq(18)
    yield dut.core.initiator.vsync_end.storage.eq(20)
    yield dut.core.initiator.vscan.storage.eq(24)
    
    yield dut.core.initiator.base.storage.eq(0)
    yield dut.core.initiator.end.storage.eq(16*16-1)
    
    yield
    yield dut.core.initiator.enable.storage.eq(1)
    yield
    datas = []
    for i in range(4096):
        if ((yield dut.core.source.valid) and
            (yield dut.core.source.ready) and
            (yield dut.core.source.de)):
            datas.append((yield dut.core.source.data))
        yield
    errors = 0
    last = -1
    for data in datas:
        if (data != (last + 1)%256):
            errors += 1
        last = data
    print("errors: {:d}".format(errors))


if __name__ == "__main__":
    tb = TB()
    mem = DRAMMemory(32, 1024, [i for i in range(256)])
    generators = {
        "sys" :   [main_generator(tb),
                   mem.read_generator(tb.dram_port)]
    }
    clocks = {"sys": 10}
    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
