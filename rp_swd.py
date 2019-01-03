# SWD interface for the Iosoft Reporta project
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
import time, rp_ftd2xx as driver

VERBOSE  = False    # Flag to display SWD read/write cycles
ERRVAL = 0xEEEEEEEE # Dummy value returned if read cycle fails

SWD_DP          = 0     # AP/DP flag bits
SWD_AP          = 1

SWD_ACK_OK      = 1     # SWD Ack values
SWD_ACK_WAIT    = 2
SWD_ACK_ERROR   = 4

# Commands to read, write, and read+write SPI data
SPI_WR_BYTES        = (driver.FTDI_SPI_WR_CLK_NEG |
                       driver.FTDI_SPI_LSB_FIRST |
                       driver.FTDI_SPI_WR_TDI)
SPI_RD_BYTES        = (driver.FTDI_SPI_LSB_FIRST |
                       driver.FTDI_SPI_RD_TDO)
SPI_RD_WR_BYTES     = SPI_RD_BYTES | SPI_WR_BYTES
SPI_RD_BITS         = SPI_RD_BYTES | driver.FTDI_SPI_BIT_MODE
SPI_WR_BITS         = SPI_WR_BYTES | driver.FTDI_SPI_BIT_MODE
SPI_RD_WR_BITS      = SPI_RD_BITS | SPI_WR_BITS

# Class for a multi-bit value
class Bitval(object):
    def __init__(self, value, nbits, name="", rd=False):
        self.value = value
        self.nbits = nbits
        self.name = name
        self.rd = rd

# Send SWD reset; at least 50 high bits, around 0111 1001 1110 0111
# (9E E7 lsb-first), then at least 2 null bits
def swd_reset(d):
    rst = (0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF, 0x9E,0xE7,
           0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF)
    driver.spi_write_bytes(d, SPI_WR_BYTES, rst)
    driver.spi_write_bits(d, SPI_WR_BITS, 0, 4)

# Send a number of idle (zero) bytes
def swd_idle_bytes(d, n):
    data = n * [0]
    driver.spi_write_bytes(d, SPI_WR_BYTES, data)

# Create an SWD read request for a given AP or DP address
class swd_rd_request(object):
    def __init__(self, ap, addr):
        addr >>= 2
        hpar = ap ^ 1 ^ (addr & 1) ^ (addr>>1 & 1)
        self.ack = Bitval(0, 3, "Ack", 1)
        self.data = Bitval(0, 32, "Data", 1)
        self.dparity = Bitval(0, 1, "DParity", 1)
        self.bitvals = (
            Bitval(1,    1, "Start"),  Bitval(ap,   1, "AP"),
            Bitval(1, 1, "Read"),      Bitval(addr, 2, "Addr"),
            Bitval(hpar, 1, "HParity"),Bitval(0, 1, "Stop"),
            Bitval(1,    1, "Park"),   Bitval(0,    1, "Turn"),
            self.ack,                  self.data,
            self.dparity,              Bitval(0, 1, "Turn"))

    # Allow the bitval list to be iterated
    def __getitem__(self, idx):
        bv = self.bitvals[idx]
        return bv

# Create an SWD write request for a given AP or DP address
class swd_wr_request(object):
    def __init__(self, ap, addr, value):
        addr >>= 2
        hpar = ap ^ (addr & 1) ^ (addr>>1 & 1)
        self.ack = Bitval(0, 3, "Ack", 1)
        self.data = Bitval(value, 32, "Data")
        self.dparity = Bitval(parity32(value), 1, "DParity")
        self.bitvals = (
            Bitval(1,    1, "Start"),  Bitval(ap,   1, "AP"),
            Bitval(0, 1, "Read"),      Bitval(addr, 2, "Addr"),
            Bitval(hpar, 1, "HParity"),Bitval(0, 1, "Stop"),
            Bitval(1,    1, "Park"),   Bitval(0,    1, "Turn"),
            self.ack,                  Bitval(0,    1, "Turn"),
            self.data,                 self.dparity)

    # Allow the bitval list to be iterated
    def __getitem__(self, idx):
        bv = self.bitvals[idx]
        return bv

# Send an SWD read request and/or get the response
def swd_rd(d, ap, addr, tx=True, rx=True):
    req = swd_rd_request(ap, addr)
    ok = False
    if tx:
        spi_write_bitvals(d, req)
        ok = True
    if rx:
        ok = spi_read_bitvals(d, req)
    if VERBOSE:
        if rx:
            print("Rd %X %-7s %08lX Ack %u" % (addr, 
                   apreg_str(addr) if ap else dpreg_str(addr, 1),
                   req.data.value, req.ack.value))
        else:
            print("Rd %X %-7s" % (addr,
                  apreg_str(addr) if ap else dpreg_str(addr, 1)))
    return req if ok else None

# Send an SWD write request and/or get the response
def swd_wr(d, ap, addr, value, tx=True, rx=True):
    req = swd_wr_request(ap, addr, value)
    ok = False
    if tx:
        spi_write_bitvals(d, req)
        ok = True
    if rx:
        ok = spi_read_bitvals(d, req)
    if VERBOSE:
        if rx:
            print("Wr %X %-7s %08lX Ack %u" % (addr, 
                  apreg_str(addr) if ap else dpreg_str(addr, 0),
                  req.data.value, req.ack.value))
        else:
            print("Wr %X %-7s %08lX" % (addr,
                  apreg_str(addr) if ap else dpreg_str(addr, 0),
                  req.data.value))
    return req if ok else None

# Write bitval requests
def spi_write_bitvals(d, bitvals):
    for bv in bitvals:
        spi_write_bitval(d, bv)

# Read bitval responses
def spi_read_bitvals(d, bitvals):
    ok = True
    driver.write_flush(d)
    for bv in bitvals:
        ok = spi_read_bitval(d, bv)
        if not ok:
            break
    return ok

# Write a bit value to SPI interface
# If read-flag is set, use read+write, otherwise just write
def spi_write_bitval(d, bv):
    value, nbits = bv.value, bv.nbits
    cmd = SPI_RD_WR_BITS if bv.rd else SPI_WR_BITS
    while nbits > 0:
        n = min(nbits, 8)
        driver.spi_write_bits(d, cmd, value&0xff, n)
        value >>= n
        nbits -= n

# Read a bit value (max 32 bits) from SPI if read-flag is set
def spi_read_bitval(d, bv):
    ok = True
    if bv.rd:
        bv.value = shift = 0
        nbits = bv.nbits
        while ok and nbits >= 8:    # Get whole bytes
            data = driver.spi_read_bytes(d, 1)
            if len(data) > 0:
                byt = data[0] >> max(8-nbits, 0)
                bv.value |= byt << shift
                shift += 8
                nbits -= 8
            else:
                bv.value = ERRVAL
                ok = False
        if ok and nbits>0:          # Get remaining bits
            data = driver.spi_read_bits(d, nbits)
            if len(data) > 0:
                bv.value = data[0]
            else:
                bv.value = ERRVAL
                ok = False
    return ok

# Display bitvar values
def disp_bitvars(bvs):
    if bvs is None:
        print("No response")
    else:
        for bv in bvs:
            print("%-8s %8X" % (bv.name, bv.value))

# Calculate parity of 32-bit integer
def parity32(i):
    i = i - ((i >> 1) & 0x55555555)
    i = (i & 0x33333333) + ((i >> 2) & 0x33333333)
    i = (((i + (i >> 4)) & 0x0F0F0F0F) * 0x01010101) >> 24
    return i & 1

# Return DP register string
def dpreg_str(reg, rd):
    if rd:
        s = ("IDCODE" if reg==0 else "STATUS" if reg==4 else
             "RESEND" if reg==8 else "RDBUFF")
    else:
        s = ("ABORT " if reg==0 else "CTRL" if reg==4 else
             "SELECT" if reg==8 else "RDBUFF")
    return s

# Return AP register string; see Cortex-M3 'AHB-AP programmers model'
def apreg_str(reg):
    return ("CSW/BD0" if reg==0 else "TAR/BD1" if reg==4 else
            "BD2/RAR" if reg==8 else "DRW/BD3")

if __name__ == "__main__":
    #driver.VERBOSE = True
    VERBOSE = True
    dev = driver.open()
    if not dev:
        print("Can't open FTDI device")
    else:
        typ, desc = driver.device_type_desc(dev)
        print("%s device in %s" % (typ, desc))
        driver.spi_init(dev)
        if not driver.check_sync(dev):
            print("Sync failed: check device supports MPSSE")
        else:
            swd_reset(dev)                       # Reset
            swd_rd(dev, SWD_DP, 0x0)             # Get ID
            swd_wr(dev, SWD_DP, 0x0, 0x1e)       # Clear errors
            swd_wr(dev, SWD_DP, 0x4, 0x50000000) # Powerup request
            swd_rd(dev, SWD_DP, 0x4)
        time.sleep(0.1)
        driver.close(dev)

# EOF

