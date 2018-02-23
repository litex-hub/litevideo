from PIL import Image

import random
from copy import deepcopy

from migen import *

from litex.soc.interconnect.stream import *

class RAWImage:
    def __init__(self, coefs, filename=None, size=None):
        self.r = None
        self.g = None
        self.b = None

        self.y = None
        self.cb = None
        self.cr = None

        self.data = []

        self.coefs = coefs
        self.size = size
        self.length = None

        if filename is not None:
            self.open(filename)


    def open(self, filename):
        img = Image.open(filename)
        if self.size is not None:
            img = img.resize((self.size, self.size), Image.ANTIALIAS)
        r, g, b = zip(*list(img.getdata()))
        self.set_rgb(r, g, b)


    def save(self, filename):
        img = Image.new("RGB" ,(self.size, self.size))
        img.putdata(list(zip(self.r, self.g, self.b)))
        img.save(filename)


    def set_rgb(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b
        self.length = len(r)


    def set_ycbcr(self, y, cb, cr):
        self.y = y
        self.cb = cb
        self.cr = cr
        self.length = len(y)


    def set_data(self, data):
        self.data = data


    def pack_rgb(self):
        self.data = []
        for i in range(self.length):
            data = (self.r[i] & 0xff) << 16
            data |= (self.g[i] & 0xff) << 8
            data |= (self.b[i] & 0xff) << 0
            self.data.append(data)
        return self.data


    def pack_ycbcr(self):
        self.data = []
        for i in range(self.length):
            data = (self.y[i] & 0xff) << 16
            data |= (self.cb[i] & 0xff) << 8
            data |= (self.cr[i] & 0xff) << 0
            self.data.append(data)
        return self.data

    def pack_rgb16f(self):
        self.data = []
        for i in range(self.length):
            data  = (self.rf[i] & 0xffff) << 32
            data |= (self.gf[i] & 0xffff) << 16
            data |= (self.bf[i] & 0xffff) << 0
            self.data.append(data)
        return self.data


    def unpack_rgb(self):
        self.r = []
        self.g = []
        self.b = []
        for data in self.data:
            self.r.append((data >> 16) & 0xff)
            self.g.append((data >> 8) & 0xff)
            self.b.append((data >> 0) & 0xff)
        return self.r, self.g, self.b


    def unpack_ycbcr(self):
        self.y = []
        self.cb = []
        self.cr = []
        for data in self.data:
            self.y.append((data >> 16) & 0xff)
            self.cb.append((data >> 8) & 0xff)
            self.cr.append((data >> 0) & 0xff)
        return self.y, self.cb, self.cr

    def unpack_rgb16f(self):
        self.rf = []
        self.gf = []
        self.bf = []
        for data in self.data:
            self.rf.append((data >> 32) & 0xffff)
            self.gf.append((data >> 16) & 0xffff)
            self.bf.append((data >> 0 ) & 0xffff)
        return self.rf, self.gf, self.bf

    # Model for our implementation
    def rgb2ycbcr_model(self):
        self.y  = []
        self.cb = []
        self.cr = []
        for r, g, b in zip(self.r, self.g, self.b):
            yraw = self.coefs["ca"]*(r-g) + self.coefs["cb"]*(b-g) + g
            self.y.append(int(yraw + self.coefs["yoffset"]))
            self.cb.append(int(self.coefs["cc"]*(b-yraw) + self.coefs["coffset"]))
            self.cr.append(int(self.coefs["cd"]*(r-yraw) + self.coefs["coffset"]))
        return self.y, self.cb, self.cr


    # Wikipedia implementation used as reference
    def rgb2ycbcr(self):
        self.y = []
        self.cb = []
        self.cr = []
        for r, g, b in zip(self.r, self.g, self.b):
            self.y.append(int(0.299*r + 0.587*g + 0.114*b))
            self.cb.append(int(-0.1687*r - 0.3313*g + 0.5*b + 128))
            self.cr.append(int(0.5*r - 0.4187*g - 0.0813*b + 128))
        return self.y, self.cb, self.cr


    # Model for our implementation
    def ycbcr2rgb_model(self):
        self.r = []
        self.g = []
        self.b = []
        for y, cb, cr in zip(self.y, self.cb, self.cr):
            self.r.append(int(y - self.coefs["yoffset"] + (cr - self.coefs["coffset"])*self.coefs["acoef"]))
            self.g.append(int(y - self.coefs["yoffset"] + (cb - self.coefs["coffset"])*self.coefs["bcoef"] + (cr - self.coefs["coffset"])*self.coefs["ccoef"]))
            self.b.append(int(y - self.coefs["yoffset"] + (cb - self.coefs["coffset"])*self.coefs["dcoef"]))
        return self.r, self.g, self.b


    # Wikipedia implementation used as reference
    def ycbcr2rgb(self):
        self.r = []
        self.g = []
        self.b = []
        for y, cb, cr in zip(self.y, self.cb, self.cr):
            self.r.append(int(y + (cr - 128) *  1.402))
            self.g.append(int(y + (cb - 128) * -0.34414 + (cr - 128) * -0.71414))
            self.b.append(int(y + (cb - 128) *  1.772))
        return self.r, self.g, self.b

    # Convert 16 bit float to 8 bit pixel
    def rgb16f2rgb_model(self):
        self.r = []
        self.g = []
        self.b = []
        for rf, gf, bf in zip(self.rf, self.gf, self.bf):
            self.r.append(float2int(rf))
            self.g.append(float2int(gf))
            self.b.append(float2int(bf))
        return self.r, self.g, self.b

    # Convert 8 bit pixel to 16 bit float
    def rgb2rgb16f_model(self):
        self.rf = []
        self.gf = []
        self.bf = []
        for r, g, b in zip(self.r, self.g, self.b):
            self.rf.append(int2float(r))
            self.gf.append(int2float(g))
            self.bf.append(int2float(b))
        return self.rf, self.gf, self.bf

def int2float(x):
    '''
    Converts a 8 bit unsigned int to 16 bit half precision floating
    point represntation.Expected input is in the range [0-255]
    Output is an 16 bit integer whose bit representation correspond
    to half precision float format.
    The value of float output is in the range [0-1]
    (higher precision in this range)
    '''
    if x==0:
        return 0
    else:
        y = bin(x)[2:].zfill(8)     # Unpack in string
        for i in range(len(y)):     # Leading one detector
            if y[i] == '1':
                shift_val = i
                break

        sign = '0'
        exp = 15 - 1 - shift_val
        frac = y[shift_val+1:][::-1].zfill(10)[::-1]
        x = sign+bin(exp)[2:].zfill(5)+frac     # Pack together in string
        z = int(x, 2)                           # Convert string to correspondinf float
        return z

def float2int(x):
    '''
    Converts a 16 bit half precision floating point represntation
    to 8 bit unsigned int.
    Output is an 16 bit integer whose bit representation correspond
    to half precision float format.
    Input is in the range [0-1]
    Expected output is in the corresponding range [0-255]

    '''
    if x==0:
        return 0
    else:
        y = bin(x)[2:].zfill(16)    # Unpack in string
        exp = y[1:6]                # Unpack exp
        frac = '1'+y[6:16]          # Unpack frac
        return int(frac,2) >> (17-int(exp,2))
