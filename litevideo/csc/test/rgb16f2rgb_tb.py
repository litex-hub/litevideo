from migen import *

from litex.soc.interconnect.stream import *
from litex.soc.interconnect.stream_sim import *

from litevideo.csc.common import *
from litevideo.csc.rgb16f2rgb import RGB16f2RGB

from litevideo.csc.test.common import *

class TB(Module):
    def __init__(self):
        self.submodules.streamer = PacketStreamer(EndpointDescription([("data", 48)]))
        self.submodules.rgb16f2rgb = RGB16f2RGB()
        self.submodules.logger = PacketLogger(EndpointDescription([("data", 24)]))

        self.comb += [
            self.streamer.source.connect(self.rgb16f2rgb.sink, omit=["data"]),
            self.rgb16f2rgb.sink.payload.rf.eq(self.streamer.source.data[32:48]),
            self.rgb16f2rgb.sink.payload.gf.eq(self.streamer.source.data[16:32]),
            self.rgb16f2rgb.sink.payload.bf.eq(self.streamer.source.data[0:16]),

            self.rgb16f2rgb.source.connect(self.logger.sink, omit=["r", "g", "b"]),
            self.logger.sink.data[16:24].eq(self.rgb16f2rgb.source.r),
            self.logger.sink.data[8:16].eq(self.rgb16f2rgb.source.g),
            self.logger.sink.data[0:8].eq(self.rgb16f2rgb.source.b)
        ]

def main_generator(dut):
#         convert image using rgb16f2rgb model
    raw_image = RAWImage(None, "lena.png", 64)
    raw_image.rgb2rgb16f_model()
    raw_image.rgb16f2rgb_model()
    raw_image.save("lena_rgb16f2rgb_reference.png")

    for i in range(24):
        yield

    # convert image using rgb16f2rgb implementation
    raw_image = RAWImage(None, "lena.png", 64)
    raw_image.rgb2rgb16f_model()
    raw_image.pack_rgb16f()
    packet = Packet(raw_image.data)
    dut.streamer.send(packet)
    yield from dut.logger.receive()
    raw_image.set_data(dut.logger.packet)
    raw_image.unpack_rgb()
    raw_image.save("lena_rgb16f2rgb.png")


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
