from migen import *

from litex.soc.interconnect.stream import *

from litedram.common import LiteDRAMPort

from litevideo.output.core import VideoOutCore


class TB(Module):
    def __init__(self):
        self.dram_port = LiteDRAMPort(mode="read", aw=32, dw=32, cd="video")
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


video_data = []

@passive
def video_capture_generator(dut):
    while True:
        if ((yield dut.core.source.valid) and
            (yield dut.core.source.ready) and
            (yield dut.core.source.de)):
            video_data.append((yield dut.core.source.data))
        yield

def main_generator(dut):
    for i in range(100):
        yield
    # init video
    yield dut.core.initiator.hres.storage.eq(16)
    yield dut.core.initiator.hsync_start.storage.eq(18)
    yield dut.core.initiator.hsync_end.storage.eq(20)
    yield dut.core.initiator.hscan.storage.eq(24)

    yield dut.core.initiator.vres.storage.eq(16)
    yield dut.core.initiator.vsync_start.storage.eq(18)
    yield dut.core.initiator.vsync_end.storage.eq(20)
    yield dut.core.initiator.vscan.storage.eq(24)

    yield dut.core.initiator.base.storage.eq(0)
    yield dut.core.initiator.length.storage.eq(16*16*4)

    yield
    yield dut.core.initiator.enable.storage.eq(1)
    yield

    # delay
    for i in range(4096):
       yield

    # check video data
    errors = 0
    last = -1
    for data in video_data:
        if (data != (last + 1)%256):
            errors += 1
            print(data)
        last = data
    print(video_data)
    print("errors: {:d}".format(errors))


if __name__ == "__main__":
    for video_clk_ns in  [20, 10, 5]:
        tb = TB()
        mem = DRAMMemory(32, 1024, [i for i in range(256)])
        generators = {
            "sys":   [main_generator(tb)],
            "video": [video_capture_generator(tb),
                      mem.read_generator(tb.dram_port)],
        }
        clocks = {"sys":   10,
                  "video": video_clk_ns}
        video_data = []
        run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
