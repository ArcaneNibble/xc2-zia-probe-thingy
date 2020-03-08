#!/usr/bin/env python3

import usb.core
import usb.util
import subprocess
import time
import json

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

def load_crbit_2(contents):
    crbit_bits = []
    for l in contents.splitlines():
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

with open('work-jed-base.jed', 'r') as f:
    work_jed_base = f.read()

with open('work-jed-alt.jed', 'r') as f:
    work_jed_alt = f.read()

ZIA_ENTRIES = [
    '01111110',
    '01111101',
    '01111011',
    '01110111',
    '01101111',
    '01011111',
    '11111111',
]

dev = JTAGInteface()
idcode = dev.idcode()
print("idcode is 0x{:08X}".format(idcode))

# dev.xc2_erase()

# crbit_bits = load_crbit('tmp-base.crbit')
# dev.xc2_program(crbit_bits)

# sys.exit(1)

work_zia_map = []

def set_fake_input_bit(shift_bits, fb, mc):
    if fb == 2:
        # Hack for inpin
        shift_bits[0] = 1
    else:
        idx = (fb * 16 + mc) * 3
        shift_bits[96 - idx] = 1

def get_output_bit(shift_bits, fb, mc):
    idx = (fb * 16 + mc) * 3 + 1
    return shift_bits[96 - idx]

def print_progress(trystr):
    # return

    # Each cell gets 15 total spaces
    print('\x1b[H', end='')
    print('\x1b[2J', end='')

    print(" " * 15, end='')
    for _ in range(zia_choices):
        print("#" * 15, end='')
    print("#")

    print(" " * 15, end='')
    for print_choice_i in range(zia_choices):
        print("# {:<13d}".format(print_choice_i), end='')
    print("#")

    print("#" * 15, end='')
    for _ in range(zia_choices):
        print("#" * 15, end='')
    print("#")

    for print_row in range(len(work_zia_map)):
        print("# {:<13d}".format(print_row), end='')
        for print_choice_i in range(zia_choices):
            if print_row == zia_row and print_choice_i == zia_choice_i:
                reverse_en = '\x1b[7m'
                reverse_dis = '\x1b[0m'
                fieldval = trystr + ' ' * (13 - len(trystr))
            else:
                reverse_en = ''
                reverse_dis = ''
                zia_data = work_zia_map[print_row][print_choice_i]
                if zia_data is None:
                    fieldval = "???"
                elif zia_data == "inpin":
                    fieldval = "inpin        "
                elif zia_data[2] == "io":
                    fieldval = "FB{}_{} io".format(zia_data[0] + 1, zia_data[1] + 1)
                else:
                    fieldval = "FB{}_{} mc".format(zia_data[0] + 1, zia_data[1] + 1)
                fieldval = fieldval + ' ' * (13 - len(fieldval))

            print("#{} {}{}".format(reverse_en, fieldval, reverse_dis), end='')
        print("#")

    print("#" * 15, end='')
    for _ in range(zia_choices):
        print("#" * 15, end='')
    print("#")

for _ in range(40):
    work_zia_map.append([None] * 6)

GCK0_FB = 1
GCK0_MC = 4

# for zia_row in range(len(work_zia_map)):
for zia_row in [6]:
    zia_choices = len(work_zia_map[zia_row])
    for zia_choice_i in range(zia_choices):
    # for zia_choice_i in [0, 1]:
        # Save current progress
        with open("zia_work_dump.json", 'w') as f:
            json.dump(work_zia_map, f, sort_keys=True, indent=4, separators=(',', ': '))

        # Generate JEDs
        jed_zia_data = ZIA_ENTRIES[-1] * zia_row + ZIA_ENTRIES[zia_choice_i] + ZIA_ENTRIES[-1] * (39 - zia_row)
        # print(jed_zia_data)
        assert len(jed_zia_data) == 8 * 40
        jed_pterm_data = '11' * zia_row + '01' + '11' * (39 - zia_row)
        # print(jed_pterm_data)
        assert len(jed_pterm_data) == 80
        this_work_base_jed = work_jed_base.format(zia=jed_zia_data, pterm=jed_pterm_data)
        this_work_alt_jed = work_jed_alt.format(zia=jed_zia_data, pterm=jed_pterm_data)

        with open('tmp-base.jed', 'w') as f:
            f.write(this_work_base_jed)
        with open('tmp-alt.jed', 'w') as f:
            f.write(this_work_alt_jed)

        base_crbit = load_crbit_2(subprocess.check_output([
            '/home/rqou/code/openfpga/src/xc2bit/target/release/xc2jed2crbit',
            'tmp-base.jed']).decode('ascii'))
        # print(base_crbit)
        alt_crbit = load_crbit_2(subprocess.check_output([
            '/home/rqou/code/openfpga/src/xc2bit/target/release/xc2jed2crbit',
            'tmp-alt.jed']).decode('ascii'))
        # print(alt_crbit)

        # Flash the bitstream here
        dev.go_tlr()
        dev.xc2_erase()
        dev.xc2_program(base_crbit)

        dev.rti_from_tlr()
        dev.shift_ir_from_rti()
        dev.shift_bits(num2arr(INTEST, 8), True)

        found_zia_entry = None

        # Need to be in exit1 state in intest mode at this point

        print_progress("inpin")
        # IO = 0
        fake_in_bits = [0] * 97
        dev.shift_dr_from_exit1()
        dev.shift_bits(fake_in_bits, True)
        # in exit1-dr state now, need to update and recapture
        dev.shift_dr_from_exit1()
        # Overlap with shifting in the next test
        # IO = 1
        set_fake_input_bit(fake_in_bits, 2, 0)
        captured_out_bits = dev.shift_bits(fake_in_bits, True)
        watcher_out_pin_0 = get_output_bit(captured_out_bits, 0, 8)

        # in exit1-dr state now, need to update and recapture
        dev.shift_dr_from_exit1()
        captured_out_bits = dev.shift_bits([0] * 97, True)
        watcher_out_pin_1 = get_output_bit(captured_out_bits, 0, 8)

        if watcher_out_pin_0 == 0 and watcher_out_pin_1 == 1:
            # Found it!
            found_zia_entry = 'inpin'

        if found_zia_entry is None:
            for try_fb in range(2):
                for try_mc in range(16):
                    if try_fb == GCK0_FB and try_mc == GCK0_MC:
                        continue

                    # Need to be in exit1 state in intest mode at this point

                    print_progress("FB{}_{} io".format(try_fb + 1, try_mc + 1))

                    # IO = 0; GCK0 = 0
                    fake_in_bits = [0] * 97
                    dev.shift_dr_from_exit1()
                    dev.shift_bits(fake_in_bits, True)
                    # in exit1-dr state now, need to update and recapture
                    dev.shift_dr_from_exit1()
                    # Overlap with shifting in the next test
                    # IO = 1; GCK0 = 0
                    set_fake_input_bit(fake_in_bits, try_fb, try_mc)
                    captured_out_bits = dev.shift_bits(fake_in_bits, True)
                    # print(captured_out_bits)
                    watcher_out_pin_00 = get_output_bit(captured_out_bits, 0, 8)

                    # in exit1-dr state now, need to update and recapture
                    dev.shift_dr_from_exit1()
                    # Overlap with shifting in the next test
                    # IO = 0; GCK0 = 1
                    fake_in_bits = [0] * 97
                    set_fake_input_bit(fake_in_bits, GCK0_FB, GCK0_MC)
                    captured_out_bits = dev.shift_bits(fake_in_bits, True)
                    # print(captured_out_bits)
                    watcher_out_pin_10 = get_output_bit(captured_out_bits, 0, 8)

                    if watcher_out_pin_00 == 0 and watcher_out_pin_10 == 1:
                        # Found it!
                        found_zia_entry = (try_fb, try_mc, 'io')
                        break

                    print_progress("FB{}_{} mc".format(try_fb + 1, try_mc + 1))

                    # in exit1-dr state now, need to update and recapture
                    dev.shift_dr_from_exit1()
                    # Overlap with shifting in the next test
                    # IO = 1; GCK0 = 1
                    fake_in_bits = [0] * 97
                    set_fake_input_bit(fake_in_bits, try_fb, try_mc)
                    set_fake_input_bit(fake_in_bits, GCK0_FB, GCK0_MC)
                    captured_out_bits = dev.shift_bits(fake_in_bits, True)
                    # print(captured_out_bits)
                    watcher_out_pin_01 = get_output_bit(captured_out_bits, 0, 8)

                    # in exit1-dr state now, need to update and recapture
                    dev.shift_dr_from_exit1()
                    captured_out_bits = dev.shift_bits([0] * 97, True)
                    # print(captured_out_bits)
                    watcher_out_pin_11 = get_output_bit(captured_out_bits, 0, 8)

                    if watcher_out_pin_01 == 0 and watcher_out_pin_11 == 1:
                        # Found it!
                        found_zia_entry = (try_fb, try_mc, 'mc')
                        break

                if found_zia_entry is not None:
                    break

        if found_zia_entry is not None:
            work_zia_map[zia_row][zia_choice_i] = found_zia_entry

# Save final progress
with open("zia_work_dump.json", 'w') as f:
    json.dump(work_zia_map, f, sort_keys=True, indent=4, separators=(',', ': '))

# HACK
zia_row = 1000000
print_progress("FAKE")

dev.go_tlr()

# led_idx = 0
# while True:
#     # In shift-dr state now

#     bits_to_shift = [0] * ((4 + led_idx) * 3)
#     bits_to_shift += [0, 1, 1]
#     bits_to_shift += [0] * ((16 + 11 - led_idx) * 3)
#     bits_to_shift = [0] + bits_to_shift[::-1]
#     led_idx = (led_idx + 1) % 8

#     # print(led_idx)
#     # print(bits_to_shift)
#     # print(len(bits_to_shift))
#     assert len(bits_to_shift) == 97

#     bits_out = dev.shift_bits(bits_to_shift, True)
#     # print(bits_out)
#     # In exit1-dr state now

#     # Hack; need to cycle through update
#     dev.shift_dr_from_exit1()

#     inpin = bits_out[0]
#     oe = bits_out[1::3][::-1]
#     fbmc_out = bits_out[2::3][::-1]
#     iopad_in = bits_out[3::3][::-1]

#     print('\x1b[H', end='')
#     print('\x1b[2J', end='')
#     #      |    |    |    |    |    |    |    |    |

#     num_fbs = len(oe) // 16

#     print("          ", end='')
#     for _ in range(num_fbs):
#         print("##########", end='')
#         print("##########", end='')
#         print("##########", end='')
#     # inpin hack
#     print("##########", end='')
#     print()

#     print("          ", end='')
#     for fb in range(num_fbs):
#         print("# FB{:<2} in ".format(fb + 1), end='')
#         print("# FB{:<2} oe ".format(fb + 1), end='')
#         print("# FB{:<2} o  ".format(fb + 1), end='')
#     # inpin hack
#     print("# INPIN  ", end='')
#     print("#")

#     print("##########", end='')
#     for _ in range(num_fbs):
#         print("##########", end='')
#         print("##########", end='')
#         print("##########", end='')
#     # inpin hack
#     print("##########", end='')
#     print()

#     for mc in range(16):
#         #      |    |    |    |    |    |    |    |    |
#         print("# {:2d}      ".format(mc + 1), end='')

#         for fb in range(num_fbs):
#             print("# {:d}       ".format(iopad_in[16 * fb + mc]), end='')
#             print("# {:d}       ".format(oe[16 * fb + mc]), end='')
#             print("# {:d}       ".format(fbmc_out[16 * fb + mc]), end='')

#         if mc == 0:
#             print("# {:d}      ".format(inpin), end='')
#         else:
#             print("#        ", end='')

#         print("#")

#     print("##########", end='')
#     for _ in range(num_fbs):
#         print("##########", end='')
#         print("##########", end='')
#         print("##########", end='')
#     # inpin hack
#     print("##########", end='')
#     print()

#     time.sleep(0.05)
