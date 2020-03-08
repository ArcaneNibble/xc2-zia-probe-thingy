#!/usr/bin/env python3

import usb.core
import usb.util
import time

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
IDCODE      = 0b00000001
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
        print("go tlr")
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)

    def rti_from_tlr(self):
        print("tlr -> rti")
        self.jtag_bit(0, 0)

    def shift_dr_from_rti(self):
        print("rti -> shift dr")
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)
        self._last_bit = self.jtag_bit(0, 0)

    def shift_bits(self, bits_in, exit):
        bits_out = []
        print("shifting {} bits".format(len(bits_in)))
        for i in range(len(bits_in)):
            bits_out.append(self._last_bit)
            if exit and i == len(bits_in) - 1:
                tms = 1
            else:
                tms = 0
            self._last_bit = self.jtag_bit(tms, bits_in[i])
        return bits_out

    def shift_ir_from_rti(self):
        print("rti -> shift ir")
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)
        self._last_bit = self.jtag_bit(0, 0)

    def rti_from_exit1(self):
        print("exit1 -> rti")
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)

    def init_pulse_from_exit1_to_rti(self):
        print("exit1 -> go through dr -> rti")
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)

    def shift_dr_from_exit1(self):
        print("exit1 -> shift dr")
        self.jtag_bit(1, 0)
        self.jtag_bit(1, 0)
        self.jtag_bit(0, 0)
        self._last_bit = self.jtag_bit(0, 0)

    def idcode(self):
        self.rti_from_tlr()
        self.shift_dr_from_rti()
        print("idcode")
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
            print("shifting row {}".format(i))
            self.shift_bits(crbit_bits[i][::-1], False)
            addr_gray = i ^ (i >> 1)
            self.shift_bits(num2arr(addr_gray, 6)[::-1], True)
            self.rti_from_exit1()
            time.sleep(0.01)
            if i != len(crbit_bits) - 1:
                self.shift_dr_from_rti()

        # In RTI

        self._xc2_discharge()
        self._xc2_init_pulse()

        self.shift_ir_from_rti()
        self.shift_bits(num2arr(ISC_DISABLE, 8), True)
        self.rti_from_exit1()

        self.shift_ir_from_rti()
        self.shift_bits(num2arr(BYPASS, 8), True)
        self.go_tlr()

# def shift_ir_from_exit1(dev):
#     global _last_bit
#     print("exit1 -> shift ir")
#     jtag_bit(dev, 1, 0)
#     jtag_bit(dev, 1, 0)
#     jtag_bit(dev, 1, 0)
#     jtag_bit(dev, 0, 0)
#     _last_bit = jtag_bit(dev, 0, 0)

dev = JTAGInteface()
idcode = dev.idcode()
print("idcode is 0x{:08X}".format(idcode))

# ##### USERCODE #####
# shift_ir_from_exit1(dev)
# shift_bits(dev, num2arr(USERCODE, 8), True)
# shift_dr_from_exit1(dev)
# usercode = shift_bits(dev, [0] * 32, True)
# print("usercode is 0x{:08X}".format(arr2num(usercode)))
# go_tlr(dev)

# ##### READ #####
# shift_ir_from_exit1(dev)
# shift_bits(dev, num2arr(ISC_ENABLE, 8), True)
# rti_from_exit1(dev)
# time.sleep(0.001)

# readback_bits = []

# shift_ir_from_rti(dev)
# shift_bits(dev, num2arr(ISC_READ, 8), True)
# shift_dr_from_exit1(dev)

# for i in range(50):
#     addr_gray = i ^ (i >> 1)
#     shift_bits(dev, num2arr(addr_gray, 6)[::-1], True)
#     rti_from_exit1(dev)
#     time.sleep(0.001)
#     # Data is ready
#     shift_dr_from_rti(dev)
#     read_row = shift_bits(dev, [0] * 260, False)
#     readback_bits.append(read_row[::-1])

# # Shift in a dummy address
# shift_bits(dev, [0] * 6, True)

# # DISCHARGE
# shift_ir_from_exit1(dev)
# shift_bits(dev, num2arr(ISC_INIT, 8), True)
# rti_from_exit1(dev)
# time.sleep(0.001)

# shift_ir_from_rti(dev)
# shift_bits(dev, num2arr(ISC_INIT, 8), True)
# init_pulse_from_exit1_to_rti(dev)
# time.sleep(0.001)

# shift_ir_from_rti(dev)
# shift_bits(dev, num2arr(ISC_DISABLE, 8), True)
# rti_from_exit1(dev)

# shift_ir_from_rti(dev)
# shift_bits(dev, num2arr(BYPASS, 8), True)
# go_tlr(dev)

# # print(readback_bits)
# with open("bbb.crbit", "w") as f:
#     f.write("// DEVICE XC2C32A-4-VQ44\n\n")
#     for row in readback_bits:
#         for b in row:
#             if b:
#                 f.write("1")
#             else:
#                 f.write("0")
#         f.write("\n")



dev.xc2_erase()

##### PROGRAM #####
crbit_bits = []
with open("aaa.crbit", "r") as f:
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
print(crbit_bits)
# aaaaaaaaaaaaa

dev.xc2_program(crbit_bits)
