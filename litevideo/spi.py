# Simple Processor Interface

from litex.gen import *
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *


# layout is a list of tuples, either:
# - (name, nbits, [reset value], [alignment bits])
# - (name, sublayout)

def _convert_layout(layout):
    r = []
    for element in layout:
        if isinstance(element[1], list):
            r.append((element[0], _convert_layout(element[1])))
        else:
            r.append((element[0], element[1]))
    return r

(MODE_EXTERNAL, MODE_SINGLE_SHOT, MODE_CONTINUOUS) = range(3)


class SingleGenerator(Module, AutoCSR):
    def __init__(self, layout, mode):
        self.source = stream.Endpoint(_convert_layout(layout))
        self.busy = Signal()

        self.comb += self.busy.eq(self.source.valid)

        if mode == MODE_EXTERNAL:
            self.trigger = Signal()
            trigger = self.trigger
        elif mode == MODE_SINGLE_SHOT:
            self._shoot = CSR()
            trigger = self._shoot.re
        elif mode == MODE_CONTINUOUS:
            self._enable = CSRStorage()
            trigger = self._enable.storage
        else:
            raise ValueError
        self.sync += If(self.source.ready | ~self.source.valid, self.source.valid.eq(trigger))

        self._create_csrs(layout, self.source.payload, mode != MODE_SINGLE_SHOT)

    def _create_csrs(self, layout, target, atomic, prefix=""):
        for element in layout:
            if isinstance(element[1], list):
                self._create_csrs(element[1], atomic,
                    getattr(target, element[0]),
                    element[0] + "_")
            else:
                name = element[0]
                nbits = element[1]
                if len(element) > 2:
                    reset = element[2]
                else:
                    reset = 0
                if len(element) > 3:
                    alignment = element[3]
                else:
                    alignment = 0
                regname = prefix + name
                reg = CSRStorage(nbits + alignment, reset=reset, atomic_write=atomic,
                    alignment_bits=alignment, name=regname)
                setattr(self, "_"+regname, reg)
                self.sync += If(self.source.ready | ~self.source.valid,
                    getattr(target, name).eq(reg.storage))


# Generates integers from start to maximum-1
class IntSequence(Module):
    def __init__(self, nbits, offsetbits=0, step=1):
        sink_layout = [("maximum", nbits)]
        if offsetbits:
            sink_layout.append(("offset", offsetbits))

        self.sink = stream.Endpoint(sink_layout)
        self.source = stream.Endpoint([("value", max(nbits, offsetbits))])

        # # #

        load = Signal()
        ce = Signal()
        last = Signal()

        maximum = Signal(nbits)
        if offsetbits:
            offset = Signal(offsetbits)
        counter = Signal(nbits)

        if step > 1:
            self.comb += last.eq(counter + step >= maximum)
        else:
            self.comb += last.eq(counter + 1 == maximum)
        self.sync += [
            If(load,
                counter.eq(0),
                maximum.eq(self.sink.maximum),
                offset.eq(self.sink.offset) if offsetbits else None
            ).Elif(ce,
                If(last,
                    counter.eq(0)
                ).Else(
                    counter.eq(counter + step)
                )
            )
        ]
        if offsetbits:
            self.comb += self.source.value.eq(counter + offset)
        else:
            self.comb += self.source.value.eq(counter)

        self.submodules.fsm = fsm = FSM()
        fsm.act("IDLE",
            load.eq(1),
            self.sink.ready.eq(1),
            If(self.sink.valid,
                NextState("ACTIVE")
            )
        )
        fsm.act("ACTIVE",
            self.source.valid.eq(1),
            If(self.source.ready,
                ce.eq(1),
                If(last,
                    NextState("IDLE")
                )
            )
        )