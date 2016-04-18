from litex.gen import *

from litex.soc.interconnect.stream import *
from litex.soc.interconnect import lasmi_bus

from litevideo.output.core import VideoOutCore


class TB(Module):
    def __init__(self):
        self.lasmim = lasmi_bus.Interface(aw=32,
                                          dw=32,
                                          nbanks=1,
                                          req_queue_size=1,
                                          read_latency=1,
                                          write_latency=1)
        self.submodules.core = VideoOutCore(self.lasmim)
        self.comb += self.core.source.ready.eq(1)


class LASMIMemory:
    def __init__(self, width, depth, init=[]):
        self.width = width
        self.depth = depth
        self.mem = []
        for d in init:
            self.mem.append(d)
        for _ in range(depth-len(init)):
            self.mem.append(0)

    @passive
    def read_generator(self, lasmim):
        address = 0
        pending = 0
        while True:
            yield lasmim.req_ack.eq(0)
            yield lasmim.dat_r_ack.eq(0)
            if pending:
                yield lasmim.dat_r_ack.eq(1)
                yield lasmim.dat_r.eq(self.mem[address%self.depth])
                yield
                yield lasmim.dat_r_ack.eq(0)
                yield lasmim.dat_r.eq(0)
                pending = 0
            elif (yield lasmim.stb):
                pending = not (yield lasmim.we)
                address = (yield lasmim.adr)
                yield
                yield lasmim.req_ack.eq(1)
            yield


def main_generator(dut):
    for i in range(100):
        yield
    yield dut.core.fi._hres.storage.eq(16)
    yield dut.core.fi._hsync_start.storage.eq(18)
    yield dut.core.fi._hsync_end.storage.eq(20)
    yield dut.core.fi._hscan.storage.eq(24)
    yield dut.core.fi._vres.storage.eq(32)
    yield dut.core.fi._vsync_start.storage.eq(34)
    yield dut.core.fi._vsync_end.storage.eq(36)
    yield dut.core.fi._vscan.storage.eq(48)
    yield
    yield dut.core.fi._enable.storage.eq(1)
    yield
    for i in range(4096):
        yield


if __name__ == "__main__":
    tb = TB()
    mem = LASMIMemory(32, 1024, [i for i in range(1024)])
    generators = {
        "sys" :   [main_generator(tb),
                   mem.read_generator(tb.lasmim)]
    }
    clocks = {"sys": 10}
    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
