from migen import *

from migen.genlib.cdc import MultiReg

from litevideo.input.common import control_tokens, channel_layout
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

data_gb_tokens = [0b0100110011]

video_gb_tokens = [
    0b1011001100,  # channel 0 token
    0b0100110011,  # channel 1 token
    0b1011001100,  # channel 2 token
]

terc4_tokens = [
    0b1010011100,
    0b1001100011,
    0b1011100100,
    0b1011100010,
    0b0101110001,
    0b0100011110,
    0b0110001110,
    0b0100111100,
    0b1011001100,
    0b0100111001,
    0b0110011100,
    0b1011000110,
    0b1010001110,
    0b1001110001,
    0b0101100011,
    0b1011000011,
]

class Decoding(Module):
    def __init__(self):
        self.valid_i = Signal()
        self.input = Signal(10)
        self.valid_o = Signal()
        self.output = Record(channel_layout)

        # # #

        self.sync.pix += self.output.de.eq(1)
        for i, t in enumerate(control_tokens):
            self.sync.pix += If(self.input == t,
                self.output.de.eq(0),
                self.output.c.eq(i)
            )
        self.sync.pix += self.output.raw.eq(self.input)
        self.sync.pix += self.output.d[0].eq(self.input[0] ^ self.input[9])
        for i in range(1, 8):
            self.sync.pix += self.output.d[i].eq(self.input[i] ^
                                                 self.input[i-1] ^
                                                 ~self.input[8])
        self.sync.pix += self.valid_o.eq(self.valid_i)

terc4_layout = [("c", 2), ("de", 1), ("dgb", 1), ("vgb", 1), ("c_valid", 1), ("d", 4)]

class DecodeTERC4Channel(Module):
    def __init__(self, channel):
        self.decval = stream.Endpoint(terc4_layout)  # decoded values output
        self.data_in = Record(channel_layout)  # data input from chansync
        self.valid_in = Signal()  # valid input from chansync &|

        # decode the data path
        ### NOTE NOTE NOTE THIS IS UNTESTED
        for i, t in enumerate(terc4_tokens):
            self.sync.pix += If(self.data_in.raw == t,
                self.decval.d.eq(i)
            )

        # decode the control signals
        if channel != 1:
            self.sync.pix += [
                If(self.valid_in,
                   If(self.data_in.raw == control_tokens[0],
                      self.decval.c.eq(0),
                      self.decval.de.eq(0),
                      self.decval.dgb.eq(0),
                      self.decval.vgb.eq(0),
                      self.decval.c_valid.eq(1)
                   ).Elif(self.data_in.raw == control_tokens[1],
                          self.decval.c.eq(1),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(0),
                          self.decval.vgb.eq(0),
                          self.decval.c_valid.eq(1)
                   ).Elif(self.data_in.raw == control_tokens[2],
                          self.decval.c.eq(2),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(0),
                          self.decval.vgb.eq(0),
                          self.decval.c_valid.eq(1)
                   ).Elif(self.data_in.raw == control_tokens[3],
                          self.decval.c.eq(3),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(0),
                          self.decval.vgb.eq(0),
                          self.decval.c_valid.eq(1)
                   ).Elif(self.data_in.raw == data_gb_tokens[0],
                          self.decval.c.eq(0),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(1),
                          self.decval.vgb.eq(0),
                          self.decval.c_valid.eq(0)
                   ).Elif(self.data_in.raw == video_gb_tokens[channel],
                          self.decval.c.eq(0),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(0),
                          self.decval.vgb.eq(1),
                          self.decval.c_valid.eq(0)
                   ).Else(
                       self.decval.de.eq(1),
                       self.decval.dgb.eq(0),
                       self.decval.vgb.eq(0),
                       self.decval.c_valid.eq(0)
                   )
                ).Else(
                    self.decval.c.eq(0),
                    self.decval.de.eq(0),
                    self.decval.dgb.eq(0),
                    self.decval.vgb.eq(0),
                    self.decval.c_valid.eq(0)
                )
            ]
        else: # green channel is special
            self.sync.pix += [
                If(self.valid_in,
                   If(self.data_in.raw == control_tokens[0],
                      self.decval.c.eq(0),
                      self.decval.de.eq(0),
                      self.decval.dgb.eq(0),
                      self.decval.vgb.eq(0),
                      self.decval.c_valid.eq(1)
                   ).Elif(self.data_in.raw == control_tokens[1],
                          self.decval.c.eq(1),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(0),
                          self.decval.vgb.eq(0),
                          self.decval.c_valid.eq(1)
                   ).Elif(self.data_in.raw == control_tokens[2],
                          self.decval.c.eq(2),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(0),
                          self.decval.vgb.eq(0),
                          self.decval.c_valid.eq(1)
                   ).Elif(self.data_in.raw == control_tokens[3],
                          self.decval.c.eq(3),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(0),
                          self.decval.vgb.eq(0),
                          self.decval.c_valid.eq(1)
                   ).Elif(self.data_in.raw == data_gb_tokens[0],
                          self.decval.c.eq(0),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(1), # green channel gb tokens are ambiguous
                          self.decval.vgb.eq(1),
                          self.decval.c_valid.eq(0)
                   ).Elif(self.data_in.raw == video_gb_tokens[channel],
                          self.decval.c.eq(0),
                          self.decval.de.eq(0),
                          self.decval.dgb.eq(1), #green channel gb tokens are ambiguous
                          self.decval.vgb.eq(1),
                          self.decval.c_valid.eq(0)
                   ).Else(
                       self.decval.de.eq(1),
                       self.decval.dgb.eq(0),
                       self.decval.vgb.eq(0),
                       self.decval.c_valid.eq(0)
                   )
                ).Else(
                    self.decval.c.eq(0),
                    self.decval.de.eq(0),
                    self.decval.dgb.eq(0),
                    self.decval.vgb.eq(0),
                    self.decval.c_valid.eq(0)
                )
            ]


class DecodeTERC4(Module, AutoCSR):
    def __init__(self):
        self.valid_i = Signal()
        self.data_in0 = Record(channel_layout)
        self.data_in1 = Record(channel_layout)
        self.data_in2 = Record(channel_layout)

        self.de_o = Signal()
        self.de_hdmi = Signal()
        self.encoding_terc4 = Signal()  # 1 if encoding terc4, 0 if encoding hdmi
        self.encrypting_video = Signal()
        self.encrypting_data = Signal()

        self.dvimode = CSRStorage()  # a bit to select DVI mode "de" detection
        dvimode_bit = Signal()
        self.specials += MultiReg(self.dvimode.storage, dvimode_bit)
        self.de_r = Signal()
        self.sync.pix += [
            self.de_r.eq(self.data_in0.de)  # delay one clock to match the HDMI pipe latency
        ]
        self.comb += [
            If(dvimode_bit,
                self.de_o.eq(self.de_r)
            ).Else(
                self.de_o.eq(self.de_hdmi)
            )
        ]

        # derive video, data guardbands and control codes
        for datan in range(3):
            name = "data" + str(datan)
            dect4 = DecodeTERC4Channel(datan)
            setattr(self.submodules, name + "_dect4", dect4)
            self.comb += [
                dect4.valid_in.eq(self.valid_i),
                dect4.data_in.eq(getattr(self, "data_in" + str(datan))) # N=0..2, dataN_dect4.eq(self.data_inN)
            ]

        self.submodules.fsm = fsm = FSM(reset_state="INIT")

        self.ctl_code = Signal(4)
        self.comb += self.ctl_code.eq(Cat(self.data1_dect4.decval.c,self.data2_dect4.decval.c))  # first argument occupies lower bits of Cat
        # ctl_code is {ch2.c1,ch2.c0,ch1.c1,ch1.c0}, and first argument to occupies the LSBs

        all_vgb = Signal()
        any_cvalid = Signal()
        c2c1_dgb = Signal()
        self.comb += [
            all_vgb.eq(self.data0_dect4.decval.vgb & self.data1_dect4.decval.vgb & self.data2_dect4.decval.vgb),
            any_cvalid.eq(self.data0_dect4.decval.c_valid | self.data1_dect4.decval.c_valid | self.data2_dect4.decval.c_valid),
            c2c1_dgb.eq(self.data2_dect4.decval.dgb & self.data1_dect4.decval.dgb) # because c0 can't have a dgb
        ]
        fsm.act("INIT",
                If(all_vgb,
                    NextState("GOING_VID")
                ).Elif(self.ctl_code == 0b0101,
                    NextState("PREAM_T4")
                ).Elif(self.ctl_code == 0b0001,
                    NextState("PREAM_VID")
                ).Else(
                    NextState("INIT")
                ),
                self.encoding_terc4.eq(0),
                self.encrypting_data.eq(0),
                self.encrypting_video.eq(0),
                self.de_hdmi.eq(0)
            )
        fsm.act("PREAM_T4",
                If(all_vgb,
                   NextState("GOING_VID")
                ).Elif(c2c1_dgb,
                   NextState("GOING_T4")
                ).Elif(self.ctl_code == 0b0101,
                   NextState("PREAM_T4")
                ).Else(
                    NextState("INIT")
                ),
                self.encoding_terc4.eq(0),
                self.encrypting_data.eq(0),
                self.encrypting_video.eq(0),
                self.de_hdmi.eq(0)
                )
        fsm.act("GOING_T4",
                If(c2c1_dgb,
                   NextState("GOING_T4")
                ).Else(
                    NextState("TERC4")
                ),
                self.encoding_terc4.eq(1),
                self.encrypting_data.eq(0),
                self.encrypting_video.eq(0),
                self.de_hdmi.eq(0)
                )
        fsm.act("TERC4",
                If(any_cvalid,
                   NextState("INIT")
                ).Elif(all_vgb,
                    NextState("GOING_VID")
                ).Elif(c2c1_dgb,
                    NextState("LEAVE_T4")
                ).Else(
                    NextState("TERC4")
                ),
                self.encoding_terc4.eq(1),
                self.encrypting_data.eq(1),
                self.encrypting_video.eq(0),
                self.de_hdmi.eq(0)
                )
        fsm.act("LEAVE_T4",
                If(c2c1_dgb,
                   NextState("LEAVE_T4")
                ).Else(
                    NextState("INIT")
                ),
                self.encoding_terc4.eq(1),
                self.encrypting_data.eq(0),
                self.encrypting_video.eq(0),
                self.de_hdmi.eq(0)
                )
        fsm.act("PREAM_VID",
                If(self.ctl_code == 0b0001,
                   NextState("PREAM_VID")
                ).Elif(all_vgb,
                    NextState("GOING_VID")
                ).Else(
                    NextState("INIT")
                ),
                self.encoding_terc4.eq(0),
                self.encrypting_data.eq(0),
                self.encrypting_video.eq(0),
                self.de_hdmi.eq(0)
                )
        fsm.act("GOING_VID",
                If(all_vgb,
                   NextState("GOING_VID")
                ).Else(
                    NextState("VIDEO")
                ),
                self.encoding_terc4.eq(0),
                self.encrypting_data.eq(0),
                self.encrypting_video.eq(0),
                self.de_hdmi.eq(0)
                )
        fsm.act("VIDEO",
                If(any_cvalid,
                    NextState("INIT")
                ).Else(
                    NextState("VIDEO")
                ),
                self.encoding_terc4.eq(0),
                self.encrypting_data.eq(0),
                self.encrypting_video.eq(1),
                self.de_hdmi.eq(1)
                )
