from PIL import Image

import random
import copy
import numpy as np


from migen import *

from litex.soc.interconnect.stream import *


class RAWImage:
    def __init__(self):
        self.a = None
        self.b = None
        self.c = None

        self.data = []

        self.length = None

        self.set_value()


    def set_value(self):

        v1 = 0
        v2 = 0.24142
        print ("Add out" , v1+v2)
        print ("Mult out" , v1*v2)
        print( "Add bin", bin(float2binint(v1+v2))[2:].zfill(16) )
        print( "Mult bin", bin(float2binint(v1*v2))[2:].zfill(16) )
        a, b = ([float2binint(v1)]*5,[float2binint(v2)]*5)
        self.set_mult_in(a, b)

    def set_mult_in(self, a, b):
        self.a = a
        self.b = b
        self.length = len(a)

    def set_data(self, data):
        self.data = data

    def pack_mult_in(self):
        self.data = []
        for i in range(self.length):
            data = (self.a[i] & 0xffff) << 16
            data |= (self.b[i] & 0xffff) << 0
            self.data.append(data)
        q = bin(data)[2:].zfill(32)
        print(  q[:16]  )
        print(  q[16:32]  )
        return self.data

    def unpack_mult_in(self):
        self.c = []
        for data in self.data:
            self.c.append((data >> 0) & 0xffff)
        print(bin(self.c[1])[2:].zfill(16) )
        print(binint2float(self.c[1]))
        return self.c


def float2binint(f):
    x = int(np.float16(f).view('H'))
    return x


def binint2float(x):
    xs = bin(x)[2:].zfill(16)
    frac = '1'+xs[6:16]
    fracn = int(frac,2)
    exp = xs[1:6]
    expn = int(exp,2) -15

    if expn == -15 :        #subnormal numbers
        expn = -14
        frac = '0'+xs[6:16]
        fracn = int(frac,2)

    sign = xs[0]
    signv = int(sign,2)

    y = ((-1)**signv)*(2**(expn))*fracn*(2**(-10))
    return y
