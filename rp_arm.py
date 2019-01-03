# ARM processor definitions for Iosoft Reporta project
#
# Copyright (c) Jeremy P Bentham 2018. See iosoft.blog for more information
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function
from ctypes import Structure, Union, c_uint
import rp_swd as swd, rp_ftd2xx as driver

poll_vars = []      # List of variables to be polled

# STM32F1 address values for testing
GPIOA       = 0x40010800        # Address of GPIO Ports A - E on STM32F1
GPIOB       = 0x40010C00
GPIOC       = 0x40011000
GPIOD       = 0x40011400
GPIOE       = 0x40011800
GPIO_IDR    = 8                 # Offset of Input Data Register
GPIO_ODR    = 0xC               #           Output Data Register
GPIO_BSRR   = 0x10              #           Bit Set Reset Register
TEST_ADDR   = GPIOB+GPIO_IDR    # CPU address to be read

# Debug Port (SWD-DP) registers
# See ARM DDI 0314H "Coresight Components Technical Reference Manual"
DPORT_IDCODE        = 0x0   # ID Code / abort
DPORT_ABORT         = 0x0
DPORT_CTRL          = 0x4   # Control / status
DPORT_STATUS        = 0x4
DPORT_SELECT        = 0x8   # Select
DPORT_RDBUFF        = 0xc   # Read buffer

# Access Port (AHB-AP) registers, high nybble is bank number
# See ARM DDI 0337E: Cortex M3 Technical Reference Manual page 11-38
APORT_CSW           = 0x0   # Control status word
APORT_TAR           = 0x4   # Transfer address
APORT_DRW           = 0xc   # Data read/write
APORT_BANK0         = 0x10  # Banked registers
APORT_BANK1         = 0x14
APORT_BANK2         = 0x18
APORT_BANK3         = 0x1c
APORT_DEBUG_ROM_ADDR= 0xf8   # Address of debug ROM
APORT_IDENT         = 0xfc   # AP identification

# AHB-AP Select Register
class AP_SELECT_REG(Structure):
    _fields_ = [("DPBANKSEL",   c_uint, 4),
                ("APBANKSEL",   c_uint, 4),
                ("Reserved",    c_uint, 16),
                ("APSEL",       c_uint, 8)]
class AP_SELECT(Union):
    _fields_ = [("reg",   AP_SELECT_REG),
                ("value", c_uint)]
ap_select = AP_SELECT()

# AHB-AP Control Status Word Register
class AP_CSW_REG(Structure):
    _fields_ = [("Size",        c_uint, 3),
                ("Res1",        c_uint, 1),
                ("AddrInc",     c_uint, 2),
                ("DbgStatus",   c_uint, 1),
                ("TransInProg", c_uint, 1),
                ("MODE",        c_uint, 4),
                ("Res2",        c_uint, 13),
                ("HProt1",      c_uint, 1),
                ("Res3",        c_uint, 3),
                ("MasterType",  c_uint, 1),
                ("Res4",        c_uint, 2)]
class AP_CSW(Union):
    _fields_ = [("reg",   AP_CSW_REG),
                ("value", c_uint)]
ap_csw = AP_CSW()

# Select AP bank, do read cycle
def ap_banked_read(h, addr):
    ap_select.reg.APBANKSEL = addr >> 4;
    swd.swd_wr(h, swd.SWD_DP, DPORT_SELECT, ap_select.value)
    swd.swd_rd(h, swd.SWD_AP, addr&0xf)
    return swd.swd_rd(h, swd.SWD_AP, addr&0xf)

# Select AP bank
def ap_bank_select(h, bank):
    ap_select.reg.APBANKSEL = bank;
    swd.swd_wr(h, swd.SWD_DP, DPORT_SELECT, ap_select.value)

# Configure AP memory accesses: zero bank, and set CSW reg
def ap_config(h, size, inc=False):
    ap_bank_select(h, 0)
    ap_csw.reg.MasterType = 1
    ap_csw.reg.HProt1 = 1
    ap_csw.reg.AddrInc = 1 if inc else 0
    ap_csw.reg.Size = 0 if size==8 else 1 if size==16 else 2
    return swd.swd_wr(h, swd.SWD_AP, APORT_CSW, ap_csw.value)

# Set AP memory address
def ap_addr(h, addr):
    swd.swd_wr(h, swd.SWD_AP, APORT_TAR, addr)
    swd.swd_idle_bytes(h, 2)

# Display the bit values of a register
def disp_reg_bitvals(u):
    for r in u.reg._fields_:
        print("%-12s %X" % (r[0], getattr(u.reg, r[0])))

# Start up the CPU SWD interface, return CPU ID or error message if failed
def cpu_swd_start(h):
    id = swd.swd_rd(h, swd.SWD_DP, DPORT_IDCODE)    # Read ID code
    swd.swd_wr(h, swd.SWD_DP, DPORT_ABORT, 0x1e)    # Clear errors
    swd.swd_wr(h, swd.SWD_DP, DPORT_CTRL,  0x5<<28) # Powerup request
    r = swd.swd_rd(h, swd.SWD_DP, DPORT_STATUS)     # Get status
    return ("no ack" if id.ack.value!=swd.SWD_ACK_OK else
            "no powerup" if r.data.value>>28!=0xf else
            "%08X" % id.data.value)

# Get AP ident, return string
def cpu_ap_ident(h):
    r = ap_banked_read(h, APORT_IDENT)
    return ("no ack" if r.ack.value!=swd.SWD_ACK_OK else
            "%08X" % r.data.value)

# Do an immediate read of a 32-bit CPU memory location
def cpu_mem_read32(h, addr):
    ap_addr(h, addr)                          # Address to read
    swd.swd_rd(h, swd.SWD_AP, APORT_DRW)      # Dummy read cycle
    r = swd.swd_rd(h, swd.SWD_AP, APORT_DRW)  # Read data
    return r.data.value if r.ack.value==swd.SWD_ACK_OK else None

# Storage class for variable to be polled
class Pollvar(object):
    def __init__(self, name, addr):
        self.name, self.addr = name, addr
        self.value = None

# Add variable to the polling list
def poll_add_var(name, addr):
    poll_vars.append(Pollvar(name, addr))

# Send out poll requests
def poll_send_requests(h):
    for pv in poll_vars:
        swd.swd_wr(h, swd.SWD_AP, APORT_TAR, pv.addr, True, False)
        swd.swd_idle_bytes(h, 2)
        swd.swd_rd(h, swd.SWD_AP, APORT_DRW, True, False)
        swd.swd_rd(h, swd.SWD_AP, APORT_DRW, True, False)

# Get poll responses
def poll_get_responses(h):
    for pv in poll_vars:
        swd.swd_wr(h, swd.SWD_AP, APORT_TAR, pv.addr, False, True)
        swd.swd_rd(h, swd.SWD_AP, APORT_DRW, False, True)
        req = swd.swd_rd(h, swd.SWD_AP, APORT_DRW, False, True)
        pv.value = req.data.value if (req.data is not None and
                    req.ack.value==swd.SWD_ACK_OK) else None

if __name__ == "__main__":
    #driver.VERBOSE = True
    swd.VERBOSE = True
    dev = driver.open()
    if not dev:
        print("Can't open FTDI device")
    else:
        typ, desc = driver.device_type_desc(dev)
        print("SWD interface: %s device in %s" % (typ, desc))
        driver.spi_init(dev)
        if not driver.check_sync(dev):
            print("Sync failed: check device supports MPSSE")
        else:
            swd.swd_reset(dev)                          # Reset SWD interface
            print("DP ident: %s" % cpu_swd_start(dev))  # Start up SWD
            print("AP ident: %s" % cpu_ap_ident(dev))   # Get banked AP ID register
            ap_config(dev, 32);                         # Configure AP RAM accesses
            val = cpu_mem_read32(dev, TEST_ADDR)        # Read 32-bit value at address
            print(("Addr %08X read failed" % TEST_ADDR) if val is None else
                  ("Addr %08X value %X" % (TEST_ADDR, val)))
        driver.close(dev)

# EOF
