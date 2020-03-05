from migen import *
from migen.fhdl.specials import Tristate
from migen.genlib.cdc import MultiReg
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import chooser

from litex.soc.interconnect.csr import CSRStorage, CSRStatus, AutoCSR

_default_edid = [  # changed to be more compatible with rpi, prefer lower freq mode for lower power/bw
    0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x00, 0x05, 0xb8, 0x4e, 0x54, 0x00, 0x00, 0x00, 0x00,
    0x13, 0x1c, 0x01, 0x03, 0x80, 0x35, 0x1e, 0x78, 0x0a, 0x3d, 0x85, 0xa6, 0x56, 0x4a, 0x9a, 0x24,
    0x12, 0x50, 0x54, 0x00, 0x00, 0x00, 0xd1, 0xc0, 0xd1, 0xc0, 0xd1, 0xc0, 0xd1, 0xc0, 0xd1, 0xc0,
    0xd1, 0xc0, 0xd1, 0xc0, 0xd1, 0xc0, 0x01, 0x1d, 0x80, 0x18, 0x71, 0x38, 0x2d, 0x40, 0x53, 0x2c,
    0x45, 0x00, 0xdd, 0x0c, 0x11, 0x00, 0x00, 0x1e, 0x02, 0x3a, 0x80, 0x18, 0x71, 0x38, 0x2d, 0x40,
    0x53, 0x2c, 0x45, 0x00, 0xdd, 0x0c, 0x11, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0xfd, 0x00, 0x38,
    0x3d, 0x1e, 0x53, 0x0f, 0x00, 0x0a, 0x20, 0x20, 0x20, 0x20, 0x20, 0x20, 0x00, 0x00, 0x00, 0xfc,
    0x00, 0x41, 0x6c, 0x70, 0x68, 0x61, 0x6d, 0x61, 0x78, 0x0a, 0x20, 0x20, 0x20, 0x20, 0x01, 0x3e,

    0x02, 0x03, 0x21, 0xf1, 0x4e, 0x90, 0x04, 0x03, 0x01, 0x14, 0x12, 0x05, 0x1f, 0x10, 0x13, 0x00,
    0x00, 0x00, 0x00, 0x23, 0x09, 0x07, 0x07, 0x83, 0x01, 0x00, 0x00, 0x65, 0x03, 0x0c, 0x00, 0x10,
    0x00, 0x02, 0x3a, 0x80, 0x18, 0x71, 0x38, 0x2d, 0x40, 0x58, 0x2c, 0x45, 0x00, 0xdd, 0x0c, 0x11,
    0x00, 0x00, 0x1e, 0x01, 0x1d, 0x80, 0x18, 0x71, 0x1c, 0x16, 0x20, 0x58, 0x2c, 0x25, 0x00, 0xdd,
    0x0c, 0x11, 0x00, 0x00, 0x9e, 0x01, 0x1d, 0x00, 0x72, 0x51, 0xd0, 0x1e, 0x20, 0x6e, 0x28, 0x55,
    0x00, 0xdd, 0x0c, 0x11, 0x00, 0x00, 0x1e, 0x8c, 0x0a, 0xd0, 0x8a, 0x20, 0xe0, 0x2d, 0x10, 0x10,
    0x3e, 0x96, 0x00, 0xdd, 0x0c, 0x11, 0x00, 0x00, 0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xba,
]


class EDID(Module, AutoCSR):
    def __init__(self, pads, default=_default_edid):
        self._hpd_notif = CSRStatus()
        self._hpd_en = CSRStorage()
        mem_size = len(default)
        assert mem_size%128 == 0
        self.specials.mem = Memory(8, mem_size, init=default)

        # # #

        # HPD
        if hasattr(pads, "hpd_notif"):
            if hasattr(getattr(pads, "hpd_notif"), "inverted"):
                hpd_notif_n = Signal()
                self.comb += hpd_notif_n.eq(~pads.hpd_notif)
                self.specials += MultiReg(hpd_notif_n, self._hpd_notif.status)
            else:
                self.specials += MultiReg(pads.hpd_notif, self._hpd_notif.status)
        else:
            self.comb += self._hpd_notif.status.eq(1)
        if hasattr(pads, "hpd_en"):
            self.comb += pads.hpd_en.eq(self._hpd_en.storage)

        # EDID
        scl_raw = Signal()
        sda_i = Signal()
        sda_raw = Signal()
        sda_drv = Signal()
        _sda_drv_reg = Signal()
        _sda_i_async = Signal()
        self.sync += _sda_drv_reg.eq(sda_drv)

        pad_scl = getattr(pads, "scl")
        if hasattr(pad_scl, "inverted"):
            self.specials += MultiReg(~pads.scl, scl_raw)
        else:
            self.specials += MultiReg(pads.scl, scl_raw)

        if hasattr(pads, "sda_pu") and hasattr(pads, "sda_pd"):
            pad_sda = getattr(pads, "sda")
            if hasattr(pad_sda, "inverted"):
                self.specials += MultiReg(~pads.sda, sda_raw)
            else:
                self.specials += MultiReg(pads.sda, sda_raw)

            self.comb += [
                pads.sda_pu.eq(0),
                pads.sda_pd.eq(_sda_drv_reg),
            ]
        else:
            self.specials += [
                Tristate(pads.sda, 0, _sda_drv_reg, _sda_i_async),
                MultiReg(_sda_i_async, sda_raw),
            ]

        # for debug
        self.scl = scl_raw
        self.sda_i = sda_i
        self.sda_o = Signal()
        self.comb += self.sda_o.eq(~_sda_drv_reg)
        self.sda_oe = _sda_drv_reg

        scl_i = Signal()
        samp_count = Signal(6)
        samp_carry = Signal()
        self.sync += [
            Cat(samp_count, samp_carry).eq(samp_count + 1),
            If(samp_carry,
                scl_i.eq(scl_raw),
                sda_i.eq(sda_raw)
            )
        ]

        scl_r = Signal()
        sda_r = Signal()
        scl_rising = Signal()
        sda_rising = Signal()
        sda_falling = Signal()
        self.sync += [
            scl_r.eq(scl_i),
            sda_r.eq(sda_i)
        ]
        self.comb += [
            scl_rising.eq(scl_i & ~scl_r),
            sda_rising.eq(sda_i & ~sda_r),
            sda_falling.eq(~sda_i & sda_r)
        ]

        start = Signal()
        self.comb += start.eq(scl_i & sda_falling)

        din = Signal(8)
        counter = Signal(max=9)
        self.sync += [
            If(start, counter.eq(0)),
            If(scl_rising,
                If(counter == 8,
                    counter.eq(0)
                ).Else(
                    counter.eq(counter + 1),
                    din.eq(Cat(sda_i, din[:7]))
                )
            )
        ]

        self.din = din
        self.counter = counter

        is_read = Signal()
        update_is_read = Signal()
        self.sync += If(update_is_read, is_read.eq(din[0]))

        offset_counter = Signal(max=mem_size)
        oc_load = Signal()
        oc_inc = Signal()
        self.sync += \
            If(oc_load,
                offset_counter.eq(din)
            ).Elif(oc_inc,
                offset_counter.eq(offset_counter + 1)
            )

        rdport = self.mem.get_port()
        self.specials += rdport
        self.comb += rdport.adr.eq(offset_counter)
        data_bit = Signal()

        zero_drv = Signal()
        data_drv = Signal()
        self.comb += \
            If(zero_drv,
                sda_drv.eq(1)
            ).Elif(data_drv,
                sda_drv.eq(~data_bit)
            )

        data_drv_en = Signal()
        data_drv_stop = Signal()
        self.sync += \
            If(data_drv_en,
                data_drv.eq(1)
            ).Elif(data_drv_stop,
                data_drv.eq(0)
            )
        self.sync += \
            If(data_drv_en,
                chooser(rdport.dat_r, counter, data_bit, 8, reverse=True)
            )

        self.submodules.fsm = fsm = FSM()

        fsm.act("WAIT_START")
        fsm.act("RCV_ADDRESS",
            If(counter == 8,
                If(din[1:] == 0x50,
                    update_is_read.eq(1),
                    NextState("ACK_ADDRESS0")
                ).Else(
                    NextState("WAIT_START")
                )
            )
        )
        fsm.act("ACK_ADDRESS0",
            If(~scl_i, NextState("ACK_ADDRESS1"))
        )
        fsm.act("ACK_ADDRESS1",
            zero_drv.eq(1),
            If(scl_i, NextState("ACK_ADDRESS2"))
        )
        fsm.act("ACK_ADDRESS2",
            zero_drv.eq(1),
            If(~scl_i,
                If(is_read,
                    NextState("READ")
                ).Else(
                    NextState("RCV_OFFSET")
                )
            )
        )

        fsm.act("RCV_OFFSET",
            If(counter == 8,
                oc_load.eq(1),
                NextState("ACK_OFFSET0")
            )
        )
        fsm.act("ACK_OFFSET0",
            If(~scl_i,
                NextState("ACK_OFFSET1")
            )
        )
        fsm.act("ACK_OFFSET1",
            zero_drv.eq(1),
            If(scl_i,
                NextState("ACK_OFFSET2")
            )
        )
        fsm.act("ACK_OFFSET2",
            zero_drv.eq(1),
            If(~scl_i,
                NextState("RCV_ADDRESS")
            )
        )

        fsm.act("READ",
            If(~scl_i,
                If(counter == 8,
                    data_drv_stop.eq(1),
                    NextState("ACK_READ")
                ).Else(
                    data_drv_en.eq(1)
                )
            )
        )
        fsm.act("ACK_READ",
            If(scl_rising,
                oc_inc.eq(1),
                If(sda_i,
                    NextState("WAIT_START")
                ).Else(
                    NextState("READ")
                )
            )
        )

        for state in fsm.actions.keys():
            fsm.act(state, If(start, NextState("RCV_ADDRESS")))
            if hasattr(pads, "hpd_en"):
                fsm.act(state, If(~self._hpd_en.storage, NextState("WAIT_START")))
