#!/usr/bin/env python3

import usb.core
import usb.util
import time

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

dev = usb.core.find(idVendor=0xf055, idProduct=0x0000)
assert dev is not None
# print(dev)

# Go into JTAG mode
dev.ctrl_transfer(0x40, 1, 0, 0, None)

def jtag_bit(dev, tms, tdi):
    val = 0
    if tdi:
        val |= 0b01
    if tms:
        val |= 0b10
    tdo = dev.ctrl_transfer(0xC0, 3, val, 0, 1)[0]
    # print("tms {} tdi {} tdo {}".format(tms, tdi, tdo))
    return tdo

_last_bit = 0

def go_tlr(dev):
    print("go tlr")
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)

def rti_from_tlr(dev):
    print("tlr -> rti")
    jtag_bit(dev, 0, 0)

def shift_dr_from_rti(dev):
    global _last_bit
    print("rti -> shift dr")
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 0, 0)
    _last_bit = jtag_bit(dev, 0, 0)

def shift_bits(dev, bits_in, exit):
    global _last_bit
    bits_out = []
    print("shifting {} bits".format(len(bits_in)))
    for i in range(len(bits_in)):
        bits_out.append(_last_bit)
        if exit and i == len(bits_in) - 1:
            tms = 1
        else:
            tms = 0
        _last_bit = jtag_bit(dev, tms, bits_in[i])
    return bits_out

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

def rti_from_exit1(dev):
    print("exit1 -> rti")
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 0, 0)

def shift_ir_from_rti(dev):
    global _last_bit
    print("rti -> shift ir")
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 0, 0)
    _last_bit = jtag_bit(dev, 0, 0)

def shift_ir_from_exit1(dev):
    global _last_bit
    print("exit1 -> shift ir")
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 0, 0)
    _last_bit = jtag_bit(dev, 0, 0)

def shift_dr_from_exit1(dev):
    global _last_bit
    print("exit1 -> shift dr")
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 0, 0)
    _last_bit = jtag_bit(dev, 0, 0)

def init_pulse_from_exit1_to_rti(dev):
    print("exit1 -> go through dr -> rti")
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 0, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 1, 0)
    jtag_bit(dev, 0, 0)

BYPASS      = 0b11111111
IDCODE      = 0b00000001
ISC_DISABLE = 0b11000000
ISC_ENABLE  = 0b11101000
ISC_PROGRAM = 0b11101010
ISC_ERASE   = 0b11101101
ISC_READ    = 0b11101110
ISC_INIT    = 0b11110000
USERCODE    = 0b11111101

go_tlr(dev)
rti_from_tlr(dev)
shift_dr_from_rti(dev)
print("idcode")
idcode = shift_bits(dev, [0] * 32, True)
print("idcode is 0x{:08X}".format(arr2num(idcode)))
# Now in exit1-dr

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

##### ERASE #####
shift_ir_from_exit1(dev)
shift_bits(dev, num2arr(ISC_ENABLE, 8), True)
rti_from_exit1(dev)
time.sleep(0.001)

shift_ir_from_rti(dev)
shift_bits(dev, num2arr(ISC_ERASE, 8), True)
rti_from_exit1(dev)
time.sleep(0.1)

# DISCHARGE
shift_ir_from_rti(dev)
shift_bits(dev, num2arr(ISC_INIT, 8), True)
rti_from_exit1(dev)
time.sleep(0.001)

shift_ir_from_rti(dev)
shift_bits(dev, num2arr(ISC_INIT, 8), True)
init_pulse_from_exit1_to_rti(dev)
time.sleep(0.001)

shift_ir_from_rti(dev)
shift_bits(dev, num2arr(ISC_DISABLE, 8), True)
rti_from_exit1(dev)

shift_ir_from_rti(dev)
shift_bits(dev, num2arr(BYPASS, 8), True)
go_tlr(dev)




##### PROGRAM #####
rti_from_tlr(dev)
shift_ir_from_rti(dev)
shift_bits(dev, num2arr(ISC_ENABLE, 8), True)
rti_from_exit1(dev)
time.sleep(0.001)

shift_ir_from_rti(dev)
shift_bits(dev, num2arr(ISC_PROGRAM, 8), True)
shift_dr_from_exit1(dev)

for i in range(len(crbit_bits)):
    # In shift-dr now
    print("shifting row {}".format(i))
    shift_bits(dev, crbit_bits[i][::-1], False)
    addr_gray = i ^ (i >> 1)
    shift_bits(dev, num2arr(addr_gray, 6)[::-1], True)
    rti_from_exit1(dev)
    time.sleep(0.01)
    if i != len(crbit_bits) - 1:
        shift_dr_from_rti(dev)

# In RTI

# DISCHARGE
shift_ir_from_rti(dev)
shift_bits(dev, num2arr(ISC_INIT, 8), True)
rti_from_exit1(dev)
time.sleep(0.001)

shift_ir_from_rti(dev)
shift_bits(dev, num2arr(ISC_INIT, 8), True)
init_pulse_from_exit1_to_rti(dev)
time.sleep(0.001)

shift_ir_from_rti(dev)
shift_bits(dev, num2arr(ISC_DISABLE, 8), True)
rti_from_exit1(dev)

shift_ir_from_rti(dev)
shift_bits(dev, num2arr(BYPASS, 8), True)
go_tlr(dev)
