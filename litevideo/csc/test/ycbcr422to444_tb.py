import random
import unittest

from migen import *
from litex.soc.interconnect.stream import *

from litevideo.csc.common import *
from litevideo.csc.ycbcr422to444 import YCbCr422to444


prng = random.Random(42)
reference_y = [prng.randrange(256) for i in range(32)]
reference_cb = []
reference_cr = []
reference_cb_cr = [prng.randrange(20, 200) for i in range(32)]
for i in range(len(reference_cb_cr)//2):
    cb = reference_cb_cr[2*i + 0]
    reference_cb.append(cb)
    reference_cb.append(cb)
for i in range(len(reference_cb_cr)//2):
    cr = reference_cb_cr[2*i + 1]
    reference_cr.append(cr)
    reference_cr.append(cr)

sink_y = reference_y
sink_cb_cr = reference_cb_cr

source_y = []
source_cb = []
source_cr = []


def sink_generator(sink, rand_threshold=100):
    prng = random.Random(42)
    for i in range(len(sink_cb_cr)):
        valid = 0
        while True:
            valid = (prng.randrange(100) < rand_threshold)
            if valid:
                yield sink.valid.eq(1)
                yield sink.y.eq(sink_y[i])
                yield sink.cb_cr.eq(sink_cb_cr[i])
                yield
                while not (yield sink.ready):
                    yield
                yield sink.valid.eq(0)
                break
            else:
                yield sink.valid.eq(0)
                yield
    # yield for processing latency
    for i in range(128):
        yield

@passive
def source_generator(source, rand_threshold=100):
    prng = random.Random(42)
    while True:
        if (yield source.ready) & (yield source.valid):
            source_y.append((yield source.y))
            source_cb.append((yield source.cb))
            source_cr.append((yield source.cr))
        ready = (prng.randrange(100) < rand_threshold)
        yield source.ready.eq(ready)
        yield

if __name__ == "__main__":
    tb = YCbCr422to444()
    generators = {"sys" :   [source_generator(tb.source),
                             sink_generator(tb.sink)]}
    clocks = {"sys": 10}

    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")

    testcase = unittest.TestCase()
    testcase.assertEqual(source_y, reference_y)
    testcase.assertEqual(source_cb, reference_cb)
    testcase.assertEqual(source_cr, reference_cr)
