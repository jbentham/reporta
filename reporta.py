# Iosoft Reporta project: passive monitoring of ARM CPU using SWD
# Requires python v2.7 or 3.x, and pyqt 4 or 5
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
#
# v0.01 JPB 27/12/18  Adapted from VarViewer v0.16

from __future__ import print_function

VERSION     = "Reporta v0.01"           # Version number to be displayed
PYQT_DISPLAY = True                     # Enable pyqt graphics

import sys, time, rp_arm as arm, rp_swd as swd, rp_ftd2xx as driver
if PYQT_DISPLAY:
    import rp_pyqt as pyqt
try:
    import Queue
except:
    import queue as Queue

POLL_DELAY  = 0.01
PORT_NAME   = "PB"                      # Name of port to be read
PORT_ADDR   = arm.GPIOB+arm.GPIO_IDR    # Address or port to be read

# Class to poll hardware. Parent is the display window
class PollTask(pyqt.QtCore.QThread):
    def __init__(self, parent=None):
        super(PollTask, self).__init__(parent)
        self.parent = parent
        pyqt.QtCore.QThread.__init__(self)
        self.running = True
        self.value = None

    # Thread to poll hardware
    def run(self):
        while self.running:
            arm.poll_send_requests(dev)
            arm.poll_get_responses(dev)
            for pv in arm.poll_vars:
                if pv.value != self.value:
                    valstr = ("%08X" % pv.value) if pv.value is not None else "?"
                    print("%8s %08X = %s" % (pv.name, pv.addr, valstr))
                    self.parent.graph_updater.emit("%s=%s" % (pv.name, valstr))
                    self.value = pv.value
            time.sleep(POLL_DELAY)

    # Stop the running thread
    def stop(self):
        if self.running:
            self.running = False
            self.wait()

if __name__ == "__main__":
    #driver.VERBOSE = True
    #swd.VERBOSE = True
    dev = driver.open()
    if not dev:
        print("Can't open FTDI device")
    else:
        typ, desc = driver.device_type_desc(dev)
        print("SWD interface: %s device in %s" % (typ, desc))
        driver.spi_init(dev)
        if not driver.check_sync(dev):
            print("Sync failed: check device supports MPSSE")
        elif not PYQT_DISPLAY:
            arm.swd.swd_reset(dev)                          # Reset SWD interface
            print("DP ident: %s" % arm.cpu_swd_start(dev))  # Start up SWD
            print("AP ident: %s" % arm.cpu_ap_ident(dev))   # Get banked AP ID register
            arm.ap_config(dev, 32);                         # Configure AP RAM accesses
            val = arm.cpu_mem_read32(dev, TEST_ADDR)        # Read 32-bit value at address
            print(("Addr %08X read failed" % TEST_ADDR) if val is None else
                  ("Addr %08X value %X" % (TEST_ADDR, val)))
            print("Polling")
            arm.poll_add_var("ZERO", 0)
            arm.poll_add_var("TESTADDR", TEST_ADDR)
            for n in range(0, 4):
                arm.poll_send_requests(dev)
                arm.poll_get_responses(dev)
                for pv in arm.poll_vars:
                    valstr = ("%08X" % pv.value) if pv.value is not None else "?"
                    print("%8s %08X = %s" % (pv.name, pv.addr, valstr))
                    time.sleep(0.2)
            if not driver.check_sync(dev):
                print("Sync failed")
        else:
            app = pyqt.QtWidgets.QApplication(sys.argv)
            win = pyqt.MyWindow()
            win.show()
            print(VERSION + "\n")
            arm.swd.swd_reset(dev)                          # Reset SWD interface
            print("DP ident: %s" % arm.cpu_swd_start(dev))  # Start up SWD
            print("AP ident: %s" % arm.cpu_ap_ident(dev))   # Get banked AP ID register
            arm.ap_config(dev, 32);                         # Configure AP RAM accesses
            arm.poll_add_var(PORT_NAME, PORT_ADDR)
            polltask = PollTask(win)
            win.close_handler = polltask.stop
            polltask.start()
            app.exec_()
        driver.close(dev)

# EOF
