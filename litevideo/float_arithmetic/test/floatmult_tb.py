from migen import *

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
            self.floatmult.sink.payload.in1.eq(self.streamer.source.data[16:32]),
            self.floatmult.sink.payload.in2.eq(self.streamer.source.data[0:16]),

            self.floatmult.source.connect(self.logger.sink, omit=["out"]),
            self.logger.sink.data[0:16].eq(self.floatmult.source.out)
        ]

def main_generator(dut):

    for i in range(4):
        yield

    raw_image = RAWImage()
    raw_image.pack_mult_in()
    packet = Packet(raw_image.data)
#    print (raw_image.data)
#    print (packet)
#    print( type(packet[0]))
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
    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
