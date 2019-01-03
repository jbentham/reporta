# FTD2XX library interface for Iosoft Reporta project
# Works with Python 2.7+ and 3; the latter also needs pypiwin32 installed
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
import sys, time, codecs, ftd2xx as ftd

VERBOSE             = False # Flag to enable verbose display
BUFFERED            = True  # Flag to enable transmit buffering
FTDI_BUFFLEN        = 1024  # Buffer size
FTDI_TIMEOUT        = 1000  # Timeout for read/write operations (msec)
FTDI_LATENCY        = 2     # Latency for transferring data

SPI_CLOCK_KHZ       = 1000  # Requested SPI clock frequency (kHz)
FTDI_SPI_OUT_BITS   = 0x03  # Bit mask for SPI outputs

FTDI_MODE_BITBANG   = 1     # MPSSE modes
FTDI_MODE_MPSSE     = 2

FTDI_SPI_WR_CLK_NEG = 0x01  # SPI command bit values
FTDI_SPI_BIT_MODE   = 0x02
FTDI_SPI_RD_CLK_NEG = 0x04
FTDI_SPI_LSB_FIRST  = 0x08
FTDI_SPI_WR_TDI     = 0x10
FTDI_SPI_RD_TDO     = 0x20
FTDI_SPI_WR_TMS     = 0x40

txbuff = []                 # Transmit buffer

# Device type strings
device_types = ("FT232BM", "FT232AM", "FT100AX", "?", "FT2232C",
                "FT232R", "FT2232H", "FT4232H", "FT232H")

# Convert list of integers to a data string for USB transmission
# If Python 3, strings are unicode, so convert to 8-bit ASCII
def to_txdata(lst):
    s = "".join([chr(a) for a in lst])
    return s if sys.version_info<(3,) else codecs.latin_1_encode(s)[0]

# Convert incoming USB data to a list of integers
# Data could be a string or byte array
def from_rxdata(data):
    return [ord(b) for b in data] if type(data) is str else list(data)

# Convert incoming string to displayable format (unicode for Python 3)
def from_rxstring(s):
    return codecs.latin_1_decode(s)[0]

# Open an FTDI device
def open(idx=0):
    try:
        d = ftd.open(idx)
        d.resetDevice()
        d.purge()
    except:
        d = None
    return(d)

# Close FTDI device
def close(d):
    d.close()

# Return strings with device type & description
def device_type_desc(d):
    info = d.getDeviceInfo()
    typ = device_types[info['type']] if info['type']<len(device_types) else "?"
    return typ, from_rxstring(info['description'])

# Initialise FTDI device in MPSSE SPI mode
def spi_init(d, hz=1000000):
    div = int((12000000 / (hz * 2)) - 1)
    d.setUSBParameters(FTDI_BUFFLEN, FTDI_BUFFLEN)
    d.setChars(0, 0, 0, 0)
    d.setTimeouts(FTDI_TIMEOUT, FTDI_TIMEOUT)
    d.setLatencyTimer(FTDI_LATENCY)
    d.setBitMode(0, 0)
    d.setBitMode(0, FTDI_MODE_MPSSE)
    write_cmd_word(d, 0x86, div)
    set_port(d, False, FTDI_SPI_OUT_BITS, 0x00)
    write_flush(d)

# Write SPI command and data bytes to the device
def spi_write_bytes(d, cmd, data):
    n = len(data) - 1
    write_data(d, [cmd, n&0xff, n>>8] + list(data))

# Read data bytes back from SPI
def spi_read_bytes(d, nbytes):
    return read_data(d, nbytes)

# Write SPI command and up to 8 bits to the device
def spi_write_bits(d, cmd, byt, nbits):
    write_data(d, (cmd, nbits-1, byt))

# Read data bits back from SPI
# Bits are left-justified in the returned byte, so must be shifted down
def spi_read_bits(d, nbits):
    data = read_data(d, 1)
    return [data[0] >> (8-nbits)] if len(data)>0 else []

# Check FTDI Rx data is in sync with Tx, return False if not
def check_sync(d):
    write_data(d, (0xAA,))
    write_flush(d)
    data = read_data(d)
    return data == [0xFA, 0xAA]

# Send command to return port status
def get_port(d, hi):
    write_data(d, ((0x83 if hi else 0x81),))

# Set I/O  port pins; low port is AD, high port is AC
# Direction bits are 1 for output, 0 for input
# SPI clock and MOSI pins must be outputs for SPI to work
def set_port(d, hi, dirn, val):
    write_data(d, ((0x82 if hi else 0x80), val, dirn))

# Set I/O port pins, protecting the SPI line directions
def set_io_pins(d, hi, dirn, val):
    dirn = dirn if hi else (dirn & 0xf8) | 3
    set_port(d, hi, dirn, val)

# Send command byte and data word
def write_cmd_word(d, cmd, w):
    write_data(d, (cmd, w&0xff, w>>8))

# Write data (a list of integers) to device
def write_data(d, data):
    global txbuff
    if VERBOSE:
        print("Tx: %s" % data_str(data))
    if BUFFERED:
        txbuff += data
    else:
        d.write(to_txdata(data))

# Flush the transmit buffer, if buffering is enabled
def write_flush(d):
    global txbuff
    d.write(to_txdata(txbuff))
    txbuff = []

# Read data from device, return list of integers
def read_data(d, nbytes=FTDI_BUFFLEN):
    data = d.read(nbytes)
    if VERBOSE:
        print("Rx: %s" % data_str(data))
    return from_rxdata(data)

# Convert data to a displayable string of hex bytes
# Data can be a string of bytes or array of ints
def data_str(data):
    return "".join(["%02X " % (ord(b) if type(b) is str else b) for b in data])

# Main program outputs SPI data to MikroElektronika UT-L 7-SEG R display
# FTDI C232HM cable: yellow to pin 6 MOSI, orange to pin 4 SCK, grey to pin 3 LE
# Pin 16 must also be powered (PWM brightness control)
if __name__ == "__main__":
    dig_segs = (0x3F,0x06,0x5B,0x4F,0x66,0x6D,0x7D,0x07,0x7F,0x6F)
    OE_MASK, LE_MASK = 0x08, 0x10
    dev = open()
    if not dev:
        print("Can't open FTDI device")
    else:
        typ, desc = device_type_desc(dev)
        print("%s device in %s" % (typ, desc))
        spi_init(dev)
        if not check_sync(dev):
            print("Sync failed: check device supports MPSSE")
        else:
            set_io_pins(dev, False, LE_MASK+OE_MASK, OE_MASK)
            for num in range(0, 101):
                data = (dig_segs[num%10], dig_segs[(num%100)//10]) if 0<=num<=99 else (0x80, 0x80)
                spi_write_bytes(dev, FTDI_SPI_WR_TDI+FTDI_SPI_WR_CLK_NEG, data)
                set_io_pins(dev, False, LE_MASK+OE_MASK, LE_MASK+OE_MASK)
                set_io_pins(dev, False, LE_MASK+OE_MASK, OE_MASK)
                write_flush(dev)
                time.sleep(0.1)
                break
        set_io_pins(dev, False, LE_MASK+OE_MASK, 0)
        write_flush(dev)
        time.sleep(0.1)
        close(dev)

# EOF
