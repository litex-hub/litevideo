from litex.gen import *
from litex.soc.interconnect.stream import *
from litex.soc.interconnect.stream_sim import *

from litevideo.float_arithmetic.common import *
from litevideo.float_arithmetic.floatmult import FloatMult
from litevideo.float_arithmetic.test.common import *

class TB(Module):
    def __init__(self):
        self.submodules.streamer = PacketStreamer(EndpointDescription([("data", 32)]))
        self.submodules.floatmult = FloatMult()
        self.submodules.logger = PacketLogger(EndpointDescription([("data", 16)]))

        self.comb += [
            self.streamer.source.connect(self.floatmult.sink, omit=["data"]),
            self.floatmult.sink.payload.a.eq(self.streamer.source.data[16:32]),
            self.floatmult.sink.payload.b.eq(self.streamer.source.data[0:16]),

            self.floatmult.source.connect(self.logger.sink, omit=["c"]),
            self.logger.sink.data[0:16].eq(self.floatmult.source.c)
        ]

def main_generator(dut):

    for i in range(48):
        yield

    raw_image = RAWImage()
    raw_image.pack_mult_in()
    packet = Packet(raw_image.data)
    dut.streamer.send(packet)
    yield from dut.logger.receive()
    raw_image.set_data(dut.logger.packet)
    raw_image.unpack_mult_in()


if __name__ == "__main__":
    tb = TB()
    generators = {"sys" : [main_generator(tb)]}
    generators = {
        "sys" :   [main_generator(tb),
                   tb.streamer.generator(),
                   tb.logger.generator()]
    }
    clocks = {"sys": 10}
    run_simulation(tb, generators, clocks, vcd_name="sim2.vcd")