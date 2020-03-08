#!/usr/bin/env python3

import usb.core
import usb.util
import time

def load_crbit(fn):
    crbit_bits = []
    with open(fn, "r") as f:
        for l in f.readlines():
            l = l.strip()
            if not l:
                continue
            if l.startswith("//"):
                continue
            # print(l)
            linebits = [1 if c == '1' else 0 for c in l]
            # print(linebits)
            assert len(linebits) == 260
            crbit_bits.append(linebits)

    assert len(crbit_bits) == 50

    return crbit_bits

def arr2num(arr):
    ret = 0
    for i in range(len(arr)):
        ret |= arr[i] << i
    return ret

def num2arr(num, bits):
    ret = []
    for i in range(bits):
        bit = num & (1 << i)
        ret.append(1 if bit else 0)
    return ret

BYPASS      = 0b11111111
EXTEST      = 0b00000000
IDCODE      = 0b00000001
INTEST      = 0b00000010
SAMPLE      = 0b00000011
ISC_DISABLE = 0b11000000
ISC_ENABLE  = 0b11101000
ISC_PROGRAM = 0b11101010
ISC_ERASE   = 0b11101101
ISC_READ    = 0b11101110
ISC_INIT    = 0b11110000
USERCODE    = 0b11111101

class JTAGInteface:
    def __init__(self):
        dev = usb.core.find(idVendor=0xf055, idProduct=0x0000)
        assert dev is not None
        # print(dev)
        self.dev = dev
        self._last_bit = 0

        # Go into JTAG mode and TLR
        dev.ctrl_transfer(0x40, 1, 0, 0, None)
        self.go_tlr()

    def jtag_bit(self, tms, tdi):
        val = 0
        if tdi:
            val |= 0b01
        if tms:
            val |= 0b10
        tdo = self.dev.ctrl_transfer(0xC0, 3, val, 0, 1)[0]
        # print("tms {} tdi {} tdo {}".format(tms, tdi, tdo))
        return tdo

    def go_tlr(self):
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)

    def rti_from_tlr(self):
        self.jtag_bit(0, 0)

    def shift_dr_from_rti(self):
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)
        self._last_bit = self.jtag_bit(0, 0)

    def shift_bits(self, bits_in, exit):
        bits_out = []
        for i in range(len(bits_in)):
            bits_out.append(self._last_bit)
            if exit and i == len(bits_in) - 1:
                tms = 1
            else:
                tms = 0
            self._last_bit = self.jtag_bit(tms, bits_in[i])
        return bits_out

    def shift_ir_from_rti(self):
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)
        self._last_bit = self.jtag_bit(0, 0)

    def rti_from_exit1(self):
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)

    def init_pulse_from_exit1_to_rti(self):
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)

    def shift_dr_from_exit1(self):
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)
        self._last_bit = self.jtag_bit(0, 0)

    def idcode(self):
        self.rti_from_tlr()
        self.shift_dr_from_rti()
        idcode = self.shift_bits([0] * 32, True)
        self.go_tlr()
        return arr2num(idcode)

    def _xc2_discharge(self):
        # DISCHARGE
        self.shift_ir_from_rti()
        self.shift_bits(num2arr(ISC_INIT, 8), True)
        self.rti_from_exit1()
        time.sleep(0.001)

    def _xc2_init_pulse(self):
        self.shift_ir_from_rti()
        self.shift_bits(num2arr(ISC_INIT, 8), True)
        self.init_pulse_from_exit1_to_rti()
        time.sleep(0.001)

    def xc2_erase(self):
        self.rti_from_tlr()
        self.shift_ir_from_rti()
        self.shift_bits(num2arr(ISC_ENABLE, 8), True)
        self.rti_from_exit1()
        time.sleep(0.001)

        self.shift_ir_from_rti()
        self.shift_bits(num2arr(ISC_ERASE, 8), True)
        self.rti_from_exit1()
        time.sleep(0.1)

        self._xc2_discharge()
        self._xc2_init_pulse()

        self.shift_ir_from_rti()
        self.shift_bits(num2arr(ISC_DISABLE, 8), True)
        self.rti_from_exit1()

        self.shift_ir_from_rti()
        self.shift_bits(num2arr(BYPASS, 8), True)
        self.go_tlr()

    def xc2_program(self, crbit_bits):
        self.rti_from_tlr()
        self.shift_ir_from_rti()
        self.shift_bits(num2arr(ISC_ENABLE, 8), True)
        self.rti_from_exit1()
        time.sleep(0.001)

        self.shift_ir_from_rti()
        self.shift_bits(num2arr(ISC_PROGRAM, 8), True)
        self.shift_dr_from_exit1()

        for i in range(len(crbit_bits)):
            # In shift-dr now
            print("shifting row {}\r".format(i), end='')
            self.shift_bits(crbit_bits[i][::-1], False)
            addr_gray = i ^ (i >> 1)
            self.shift_bits(num2arr(addr_gray, 6)[::-1], True)
            self.rti_from_exit1()
            time.sleep(0.01)
            if i != len(crbit_bits) - 1:
                self.shift_dr_from_rti()
        print()

        # In RTI

        self._xc2_discharge()
        self._xc2_init_pulse()

        self.shift_ir_from_rti()
        self.shift_bits(num2arr(ISC_DISABLE, 8), True)
        self.rti_from_exit1()

        self.shift_ir_from_rti()
        self.shift_bits(num2arr(BYPASS, 8), True)
        self.go_tlr()

dev = JTAGInteface()
idcode = dev.idcode()
print("idcode is 0x{:08X}".format(idcode))

# dev.xc2_erase()

# crbit_bits = load_crbit('test.crbit')
# dev.xc2_program(crbit_bits)

dev.rti_from_tlr()
dev.shift_ir_from_rti()
dev.shift_bits(num2arr(INTEST, 8), True)
# dev.shift_bits(num2arr(EXTEST, 8), True)
dev.shift_dr_from_exit1()

led_idx = 0
while True:
    # In shift-dr state now

    bits_to_shift = [0] * ((4 + led_idx) * 3)
    bits_to_shift += [0, 1, 1]
    bits_to_shift += [0] * ((16 + 11 - led_idx) * 3)
    bits_to_shift = [0] + bits_to_shift[::-1]
    led_idx = (led_idx + 1) % 8

    # print(led_idx)
    # print(bits_to_shift)
    # print(len(bits_to_shift))
    assert len(bits_to_shift) == 97

    bits_out = dev.shift_bits(bits_to_shift, True)
    # print(bits_out)
    # In exit1-dr state now

    # Hack; need to cycle through update
    dev.shift_dr_from_exit1()

    inpin = bits_out[0]
    oe = bits_out[1::3][::-1]
    fbmc_out = bits_out[2::3][::-1]
    iopad_in = bits_out[3::3][::-1]

    print('\x1b[H', end='')
    print('\x1b[2J', end='')
    #      |    |    |    |    |    |    |    |    |

    num_fbs = len(oe) // 16

    print("          ", end='')
    for _ in range(num_fbs):
        print("##########", end='')
        print("##########", end='')
        print("##########", end='')
    # inpin hack
    print("##########", end='')
    print()

    print("          ", end='')
    for fb in range(num_fbs):
        print("# FB{:<2} in ".format(fb + 1), end='')
        print("# FB{:<2} oe ".format(fb + 1), end='')
        print("# FB{:<2} o  ".format(fb + 1), end='')
    # inpin hack
    print("# INPIN  ", end='')
    print("#")

    print("##########", end='')
    for _ in range(num_fbs):
        print("##########", end='')
        print("##########", end='')
        print("##########", end='')
    # inpin hack
    print("##########", end='')
    print()

    for mc in range(16):
        #      |    |    |    |    |    |    |    |    |
        print("# {:2d}      ".format(mc + 1), end='')

        for fb in range(num_fbs):
            print("# {:d}       ".format(iopad_in[16 * fb + mc]), end='')
            print("# {:d}       ".format(oe[16 * fb + mc]), end='')
            print("# {:d}       ".format(fbmc_out[16 * fb + mc]), end='')

        if mc == 0:
            print("# {:d}      ".format(inpin), end='')
        else:
            print("#        ", end='')

        print("#")

    print("##########", end='')
    for _ in range(num_fbs):
        print("##########", end='')
        print("##########", end='')
        print("##########", end='')
    # inpin hack
    print("##########", end='')
    print()

    time.sleep(0.05)
