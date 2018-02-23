from migen import *

from litex.soc.interconnect.stream import *
from litex.soc.interconnect.stream_sim import *

from litevideo.csc.common import *
from litevideo.csc.rgb2rgb16f import RGB2RGB16f

from litevideo.csc.test.common import *

class TB(Module):
    def __init__(self):
        self.submodules.streamer = PacketStreamer(EndpointDescription([("data", 24)]))
        self.submodules.rgb2rgb16f = RGB2RGB16f()
        self.submodules.logger = PacketLogger(EndpointDescription([("data", 48)]))

        self.comb += [
            self.streamer.source.connect(self.rgb2rgb16f.sink, omit=["data"]),
            self.rgb2rgb16f.sink.payload.r.eq(self.streamer.source.data[16:24]),
            self.rgb2rgb16f.sink.payload.g.eq(self.streamer.source.data[8:16]),
            self.rgb2rgb16f.sink.payload.b.eq(self.streamer.source.data[0:8]),

            self.rgb2rgb16f.source.connect(self.logger.sink, omit=["rf", "gf", "bf"]),
            self.logger.sink.data[32:48].eq(self.rgb2rgb16f.source.rf),
            self.logger.sink.data[16:32].eq(self.rgb2rgb16f.source.gf),
            self.logger.sink.data[ 0:16].eq(self.rgb2rgb16f.source.bf)
        ]


def main_generator(dut):
        # convert image using rgb2ycbcr model
        raw_image = RAWImage(None, "lena.png", 64)
        raw_image.rgb2rgb16f_model()
        raw_image.rgb16f2rgb_model()
        raw_image.save("lena_rgb2rgb16f_reference.png")

        for i in range(24):
            yield

        # convert image using rgb2ycbcr implementation
        raw_image = RAWImage(None, "lena.png", 64)
        raw_image.pack_rgb()
        packet = Packet(raw_image.data)
        dut.streamer.send(packet)
        yield from dut.logger.receive()
        raw_image.set_data(dut.logger.packet)
        raw_image.unpack_rgb16f()
        raw_image.rgb16f2rgb_model()
        raw_image.save("lena_rgb2rgb16f.png")

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
