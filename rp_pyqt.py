# PyQT4 & 5 interface for Iosoft Reporta project
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

import sys, time
try:
    from PyQt5.QtGui import QBrush, QPen, QColor, QFont, QTextCursor, QFontMetrics, QPainter
    from PyQt5.QtWidgets import QApplication, QGraphicsScene, QGraphicsView, QGraphicsSimpleTextItem
    from PyQt5 import QtCore, QtWidgets
except:
    from PyQt4.QtGui import QBrush, QPen, QColor, QFont, QTextCursor, QFontMetrics, QPainter
    from PyQt4.QtGui import QApplication, QGraphicsScene, QGraphicsView, QGraphicsSimpleTextItem
    from PyQt4 import QtCore, QtGui as QtWidgets
Qt = QtCore.Qt
try:
    import Queue
except:
    import queue as Queue
from collections import OrderedDict

VERSION         = "Reporta"
GRID_PITCH      = 4.0
WINDOW_SIZE     = 800, 500
VIEW_SIZE       = 400, 320
FRAME_SIZE      = 120, 51
FRAME_COLOUR    = QColor(240, 240, 240)
FRAME_BRUSH     = QBrush(FRAME_COLOUR, style=Qt.Dense1Pattern)
FRAME_PEN       = QPen(Qt.gray, 0)
BOARD_GPOS      = 9, 3
BOARD_GSIZE     = 20, 7
BOARD_COLOUR    = QColor(170, 180, 220)
BOARD_PEN       = QPen(BOARD_COLOUR, 2)
BOARD_BRUSH     = QBrush(BOARD_COLOUR)
PIN_SIZE        = 0.4
SMALLPIN_SIZE   = 0.25
PIN_ON_PEN      = QPen(QColor(200, 0, 0), 0)
PIN_ON_BRUSH    = QBrush(Qt.red)
PIN_OFF_OPACITY = 0.1
PIN_ON_OPACITY  = 1
GRID_ADJ        = 2.4, 1.5
LABEL_FONT      = QFont("Courier New", 6)
LABEL_SCALE     = 0.3
LABEL_OSET      = -1.0, 0.5
SEGDISP_GPOS    = 3, 3
SEGDISP_GSIZE   = 5, 7
SEGDISP_PEN     = QPen(Qt.gray, 0.2)
SEGDISP_BRUSH   = QBrush(QColor(210, 210, 200))
SEG_WIDTH       = 2.0
SEG_PEN         = QPen(QColor(0, 160, 0), SEG_WIDTH, cap=Qt.RoundCap)
SEG_DP_PEN      = QPen(QColor(0, 160, 0), 1)
BUTTON_GPOS     = 0.5, 5.0
BUTTON_GSIZE    = 2.0, 2.0
BUTTON_OFF_PEN  = QPen(Qt.darkRed, 1)
BUTTON_OFF_BRUSH= QBrush(Qt.darkRed)
BUTTON_ON_BRUSH = QBrush(Qt.red)
BUTTON_PIN      = "PB3"

# Kingbright SC56-11LGWA 7-seg display pins, starting top left (pin 10)
# Ordered dictionary with segment letter keys, and bit number values
# Decimal point is given letter 'h', so ordinal values can be used
# Non-animated pins must have a unique letter, and -ve bit number
SEG_BITNUM = OrderedDict((("g",11), ("f",10), ("x",-1), ("a",1),  ("b",0),
                          ("e",12), ("d",13), ("y",-1), ("c",14), ("h",15)))
# 7-seg I/O port identifier
SEGPORT = "PB"

# Signal idents for 7-segment display pins, starting top left
# Non-animated pins have null ident strings
SEG_IDENTS = ["%s%u" % (SEGPORT, bitnum) if bitnum>=0 else ""
              for bitnum in SEG_BITNUM.values()]

# Dimensions of 7-seg display
D7X,D7Y     = 0.8,1.0       # Top left corner
D7W,D7H,D7L = 2.0,2.0,0.2   # X and Y seg length, and X-direction lean
SEG_DP_OSET = 4.0, 5.0      # Decimal point X, Y
SEG_DP_SIZE = 0.25          # Decimal point size

# Segment endpoints in the order F, A, B, C, D, E, G (for continous drawing)
SEG_LINES   = ((D7X+D7L, D7Y+D7H),   (D7X+D7L*2,D7Y),    (D7X+D7L*2+D7W,D7Y),
               (D7X+D7L+D7W,D7Y+D7H),(D7X+D7W,D7Y+D7H*2),(D7X,D7Y+D7H*2),
               (D7X+D7L,D7Y+D7H),    (D7X+D7L+D7W,D7Y+D7H))

# Bit pattern for 0-9 and A-F, l.s.bit is segment 'a' (only needed for testing)
num_segs  = (0x3F,0x06,0x5B,0x4F,0x66,0x6D,0x7D,0x07,
             0x7F,0x6F,0x77,0x7C,0x39,0x5E,0x79,0x71)

# STM32F103 'blue pill' board pinout, starting top left
BOARDPINS=("GND", "GND", "3V3", "NRST","PB11","PB10","PB1", "PB0", "PA7", "PA6",
           "PA5", "PA4", "PA3", "PA2", "PA1", "PA0", "PC15","PC14","PC13","VBAT",
           "PB12","PB13","PB14","PB15","PA8", "PA9", "PA10","PA11","PA12","PA15",
           "PB3", "PB4", "PB5", "PB6", "PB7", "PB8", "PB9", "5V",  "GND", "3V3")

# Convert a digit to the O/P bits driving 7-seg display
def num_segbits(num):
    segs = num_segs[num & 0xf]
    val = 0
    for n in range(0, 7):
        if segs & (1 << n):
            bitnum = SEG_BITNUM[chr(n + ord('a'))]
            val |= 1 << bitnum
    return val

# Class to provide dummy data for test. Parent is the display window
class PollTask(QtCore.QThread):
    def __init__(self, parent=None):
        super(PollTask, self).__init__(parent)
        self.parent = parent
        QtCore.QThread.__init__(self)
        self.running = True
        self.value = 0

    # Thread to generate dummy data in response to a poll request
    def run(self):
        while self.running:
            req = poll_requests.get()
            if req:
                print(req)
                val = num_segbits(self.value)
                val |= 0x8000 if self.value&1 else 0x8
                if self.parent:
                    self.parent.graph_updater.emit("%s=%X" % ("PB", val))
                self.value = (self.value + 1) % 10

# Central widget (whole display area)
class MyWidget(QtWidgets.QWidget):
    text_updater = QtCore.pyqtSignal(str)   # Signal to update text display

    # Initialise the GUI
    def __init__(self, parent=None):
        super(MyWidget, self).__init__(parent)
        self.parent = parent
        self.text = QtWidgets.QTextEdit()
        self.scene = QGraphicsScene()
        self.view = MyView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.sigpins = {}
        self.measure_text()
        self.scene.addRect(0, 0, *FRAME_SIZE, pen=FRAME_PEN, brush=FRAME_BRUSH)
        self.draw_rect(BOARD_GPOS, BOARD_GSIZE, BOARD_PEN, BOARD_BRUSH)
        self.draw_pin_labels(BOARD_GPOS, BOARD_GSIZE)
        self.draw_part_pins(BOARD_GPOS, BOARD_GSIZE, BOARDPINS, PIN_SIZE, True)
        self.draw_rect(SEGDISP_GPOS, SEGDISP_GSIZE, SEGDISP_PEN, SEGDISP_BRUSH)
        self.draw_part_pins(SEGDISP_GPOS, SEGDISP_GSIZE, SEG_IDENTS, SMALLPIN_SIZE, True)
        self.draw_part_segs(SEGDISP_GPOS)
        self.draw_button()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.view, 30)
        layout.addWidget(self.text, 10)
        self.setLayout(layout)
        self.text_updater.connect(self.update_text)
        sys.stdout = self

    # Convert x,y grid position to graphics position
    def grid_pos(self, gpos):
        return gpos[0]*GRID_PITCH + GRID_ADJ[0], gpos[1]*GRID_PITCH + GRID_ADJ[1]

    # Convert w,h grid size to graphics size
    def grid_size(self, gsize):
        return gsize[0]*GRID_PITCH, gsize[1]*GRID_PITCH

    # Add rectangle to grid, given top-left corner
    def draw_rect(self, gpos, gsize, pen=Qt.gray, brush=Qt.darkGray):
        x,y = self.grid_pos(gpos)
        w,h = self.grid_size(gsize)
        rect = self.scene.addRect(0, 0, w, h, pen, brush)
        rect.setPos(x-GRID_PITCH/2.0, y-GRID_PITCH/2.0)
        return rect

    # Add circle to grid, given centre
    def draw_circle(self, gpos, size, pen, brush=PIN_ON_BRUSH):
        size *= GRID_PITCH
        x,y = self.grid_pos(gpos)
        p = self.scene.addEllipse(0, 0, size, size, pen, brush)
        p.setPos(x-size/2.0, y-size/2.0)
        return p

    # Measure text for positioning
    def measure_text(self, txt="ABCD"):
        fm = QFontMetrics(LABEL_FONT)
        self.label_wd, self.label_ht = fm.width(txt)*LABEL_SCALE, fm.height()*LABEL_SCALE

    # Add labels to part
    def draw_pin_labels(self, gpos, gsize):
        for n, id in enumerate(BOARDPINS):
            gx = gpos[0] + n%20
            gy = gpos[1] + (0 if n<20 else gsize[1]-3)
            self.draw_label((gx, gy), id)

    # Add text label to grid
    def draw_label(self, gpos, text, font=LABEL_FONT):
        x,y = self.grid_pos(gpos)
        size = self.label_wd, self.label_ht
        txt = self.scene.addText(text, font)
        txt.setScale(LABEL_SCALE)
        txt.setTransformOriginPoint(size[0], size[1]/2.0)
        txt.setRotation(90)
        txt.setPos(x+LABEL_OSET[0]-size[0]/2.0, y+LABEL_OSET[1])

    # Add pins to a part
    def draw_part_pins(self, gpos, gsize, pins, pinsize=PIN_SIZE, animate=False):
        for n, name in enumerate(pins):
            gx = gpos[0] + n%gsize[0]
            gy = gpos[1] + (0 if n<gsize[0] else gsize[1]-1)
            p = self.draw_pin((gx, gy), pinsize)
            if animate:
                self.add_pin_signal(name, p)

    # Add signal to animation list
    def add_pin_signal(self, name, pin):
        if name not in self.sigpins:
            self.sigpins[name] = []
        self.sigpins[name].append(pin)

    # Add pin to graphics display
    def draw_pin(self, gpos, pinsize):
        p = self.draw_circle(gpos, pinsize, PIN_ON_PEN, PIN_ON_BRUSH)
        p.setOpacity(PIN_OFF_OPACITY)
        return p

    # Add segments to 7-segment display
    def draw_part_segs(self, gpos):
        x2 = y2 = None
        self.segments = []
        for line in SEG_LINES:
            x1, y1 = self.grid_pos((line[0]+gpos[0], line[1]+gpos[1]))
            if x2 is not None:
                seg = self.scene.addLine(x1, y1, x2, y2, SEG_PEN)
                seg.setOpacity(PIN_OFF_OPACITY)
                self.segments.append(seg)
            x2, y2 = x1, y1
        self.segments.insert(5, self.segments.pop(0))  # Re-order to segment A first
        dpos = SEG_DP_OSET[0]+gpos[0], SEG_DP_OSET[1]+gpos[1]
        dp = self.draw_circle(dpos, SEG_DP_SIZE, SEG_DP_PEN)
        dp.setOpacity(PIN_OFF_OPACITY)
        self.segments.append(dp)
        for n, seg in enumerate(self.segments):
            bitnum = SEG_BITNUM[chr(n + ord('a'))]
            self.add_pin_signal("%s%u" % (SEGPORT, bitnum), seg)

    # Draw pushbutton
    def draw_button(self):
        self.draw_rect(BUTTON_GPOS, BUTTON_GSIZE, BUTTON_OFF_PEN, BUTTON_OFF_BRUSH)
        gx, gy = BUTTON_GPOS[0]+BUTTON_GSIZE[0]/4, BUTTON_GPOS[1]+BUTTON_GSIZE[1]/4
        p = self.draw_circle((gx, gy), BUTTON_GSIZE[0], BUTTON_OFF_PEN, BUTTON_ON_BRUSH)
        p.setOpacity(PIN_OFF_OPACITY)
        self.add_pin_signal(BUTTON_PIN, p)
        return p

    # Set port pins on/off states
    # Space-delimited 'name=value' with 16 bit hex value, e.g. 'PA=12C PB=D3E4'
    def set_ports(self, s):
        data = str(s).split(' ')
        for d in data:
            name,eq,num = d.partition('=')
            if eq and num is not None:
                val = int(num, 16)
                print("Port %s = %X" % (name, val))
                for i in range(0, 16):
                    self.set_pin("%s%u=%X" % (name, i, (val>>i)&1))

    # Set pin (or segment) on/off state
    # Format is 'name=value', e.g.  'PA10=1'
    def set_pin(self, s):
        name, eq, num = s.partition('=')
        if eq and name in self.sigpins:
            val = int(num, 16)
            for p in self.sigpins[name]:
                if int(p.opacity()) != val:
                    p.setOpacity(PIN_ON_OPACITY if val else PIN_OFF_OPACITY)

    # Handler to update graphics display
    def update_graph(self, s):
        self.set_ports(s)

    # Handler to update text display
    def update_text(self, text):
        disp = self.text.textCursor()           # Move cursor to end
        disp.movePosition(QTextCursor.End)
        text = str(text).replace("\r", "")      # Eliminate CR
        while text:
            head,sep,text = text.partition("\n")# New line on LF
            disp.insertText(head)
            if sep:
                disp.insertBlock()
        self.text.ensureCursorVisible()    # Scroll if necessary

    # Handle sys.stdout.write: update text display
    def write(self, text):
        self.text_updater.emit(str(text))
    def flush(self):
        pass

# Subclass of graphics view to handle resizing
class MyView(QGraphicsView):
    def resizeEvent(self, event):
        super(MyView, self).resizeEvent(event)
        bounds = self.scene().itemsBoundingRect()
        self.fitInView(bounds, Qt.KeepAspectRatio)

# Window to display widget
class MyWindow(QtWidgets.QMainWindow, MyWidget):
    graph_updater = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.widget = MyWidget(self)
        self.setCentralWidget(self.widget)
        self.setWindowTitle(VERSION)
        self.resize(*WINDOW_SIZE)
        self.graph_updater.connect(self.widget.update_graph)
        self.close_handler = None

    def closeEvent(self, event):
        if self.close_handler:
            self.close_handler()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = MyWindow()
    win.show()
    print(VERSION + "\n")
    poll_requests = Queue.Queue()
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: poll_requests.put("PB?"))
    polltask = PollTask(win)
    polltask.start()
    timer.start(1000)
    sys.exit(app.exec_())

#EOF
