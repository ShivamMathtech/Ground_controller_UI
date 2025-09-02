"""
NASA-style rover controller GUI - enhanced

Features included in this single-file PyQt5 template:
 - Multi-camera frames (camera A, camera B, synthetic map view)
 - Embedded map panel (loads /mnt/data/images.jfif as placeholder)
 - Drive controls: Forward / Back / Left / Right buttons and Hold-to-drive via press/release
 - Motor speed slider (0-255) and Servo speed slider
 - Battery life progress bar, distance covered & speed readouts
 - Sensor telemetry list (simulated) and log console
 - Timeline / playback controls (for recorded playback simulation)
 - Hooks and comments showing where to plug ROS topics, serial, or websocket telecommands

Run:
 pip install pyqt5 opencv-python numpy
 python PyQt5_ROS_style_interface.py

Note: This is a desktop simulation UI focused on layout and wiring. Replace camera indices/file paths and add real telemetry sources as needed.
"""

import sys
import os
import time
import threading
import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

# Path to placeholder map image (provided in conversation assets)
MAP_IMAGE = '/mnt/data/images.jfif'

class VideoThread(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(object, np.ndarray)  # (name, frame)

    def __init__(self, name='cam', source=0, parent=None):
        super().__init__(parent)
        self.name = name
        self.source = source
        self._run = True
        self.cap = None

    def run(self):
        # source can be int (camera) or str (video file)
        try:
            self.cap = cv2.VideoCapture(self.source)
        except Exception:
            return
        if not self.cap or not self.cap.isOpened():
            return
        while self._run:
            ret, frame = self.cap.read()
            if not ret:
                # loop for files
                if isinstance(self.source, str):
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                break
            self.frame_ready.emit(self.name, frame)
            self.msleep(30)
        if self.cap:
            self.cap.release()

    def stop(self):
        self._run = False
        self.wait()

class VideoWidget(QtWidgets.QLabel):
    def __init__(self, title='', parent=None):
        super().__init__(parent)
        self.title = title
        self.setMinimumSize(240, 160)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet('background: #111; color: #eee; border: 1px solid #444;')
        self.pix = None

    def set_frame(self, frame: np.ndarray):
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_img = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qt_img).scaled(self.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        painter = QtGui.QPainter(pix)
        painter.setPen(QtGui.QPen(QtGui.QColor(255,255,255), 2))
        painter.setFont(QtGui.QFont('Sans', 10))
        painter.drawText(8, 18, self.title)
        painter.end()
        self.setPixmap(pix)

class TelemetrySimulator(QtCore.QObject):
    telemetry_updated = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = True
        self._dist = 0.0
        self._battery = 100.0
        self._speed = 0.0

    def start(self):
        # run in a separate thread to simulate sensor updates
        def loop():
            while self._run:
                # update values
                self._speed = max(0.0, min(2.5, self._speed + (np.random.randn()*0.05)))
                self._dist += self._speed * 0.1
                self._battery = max(0.0, self._battery - 0.01 - abs(self._speed)*0.001)
                payload = {
                    'timestamp': time.time(),
                    'battery': round(self._battery,1),
                    'speed': round(self._speed,2),
                    'distance': round(self._dist,2),
                    'temp': round(20 + np.random.randn(),1),
                    'gps': (77.2 + np.random.randn()*0.0001, 28.6 + np.random.randn()*0.0001)
                }
                self.telemetry_updated.emit(payload)
                time.sleep(0.5)
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def stop(self):
        self._run = False

class ControlPanel(QtWidgets.QWidget):
    drive_command = QtCore.pyqtSignal(dict)  # e.g. {'cmd':'forward', 'speed':200}

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6,6,6,6)
        layout.setSpacing(8)

        # Drive buttons (arranged like a D-pad)
        gb_drive = QtWidgets.QGroupBox('Drive')
        grid = QtWidgets.QGridLayout()
        self.btn_up = QtWidgets.QPushButton('▲')
        self.btn_down = QtWidgets.QPushButton('▼')
        self.btn_left = QtWidgets.QPushButton('◀')
        self.btn_right = QtWidgets.QPushButton('▶')
        for b in [self.btn_up, self.btn_down, self.btn_left, self.btn_right]:
            b.setAutoRepeat(True)
            b.setAutoRepeatInterval(100)
            b.setFixedSize(60,40)
        grid.addWidget(self.btn_up, 0, 1)
        grid.addWidget(self.btn_left, 1, 0)
        grid.addWidget(self.btn_right, 1, 2)
        grid.addWidget(self.btn_down, 2, 1)
        gb_drive.setLayout(grid)
        layout.addWidget(gb_drive)

        # speed sliders
        gb_speed = QtWidgets.QGroupBox('Speed / Power')
        vsp = QtWidgets.QVBoxLayout()
        self.motor_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.motor_slider.setRange(0, 255)
        self.motor_slider.setValue(180)
        self.motor_label = QtWidgets.QLabel('Motor speed: 180')
        self.motor_slider.valueChanged.connect(lambda v: self.motor_label.setText(f'Motor speed: {v}'))
        vsp.addWidget(self.motor_label)
        vsp.addWidget(self.motor_slider)

        self.servo_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.servo_slider.setRange(0, 180)
        self.servo_slider.setValue(90)
        self.servo_label = QtWidgets.QLabel('Servo angle: 90')
        self.servo_slider.valueChanged.connect(lambda v: self.servo_label.setText(f'Servo angle: {v}'))
        vsp.addWidget(self.servo_label)
        vsp.addWidget(self.servo_slider)
        gb_speed.setLayout(vsp)
        layout.addWidget(gb_speed)

        # Battery and telemetry quick view
        gb_status = QtWidgets.QGroupBox('Power')
        h = QtWidgets.QHBoxLayout()
        self.batt = QtWidgets.QProgressBar()
        self.batt.setRange(0,100)
        self.batt.setValue(100)
        self.batt.setFormat('%p%')
        h.addWidget(self.batt)
        gb_status.setLayout(h)
        layout.addWidget(gb_status)

        # Action buttons
        h2 = QtWidgets.QHBoxLayout()
        self.btn_estop = QtWidgets.QPushButton('E-STOP')
        self.btn_home = QtWidgets.QPushButton('Home')
        h2.addWidget(self.btn_estop)
        h2.addWidget(self.btn_home)
        layout.addLayout(h2)

        layout.addStretch()

        # Wiring drive signals
        self.btn_up.pressed.connect(lambda: self._emit_drive('forward'))
        self.btn_up.released.connect(lambda: self._emit_drive('stop'))
        self.btn_down.pressed.connect(lambda: self._emit_drive('back'))
        self.btn_down.released.connect(lambda: self._emit_drive('stop'))
        self.btn_left.pressed.connect(lambda: self._emit_drive('left'))
        self.btn_left.released.connect(lambda: self._emit_drive('stop'))
        self.btn_right.pressed.connect(lambda: self._emit_drive('right'))
        self.btn_right.released.connect(lambda: self._emit_drive('stop'))

        # extra actions
        self.btn_estop.clicked.connect(lambda: self._emit_drive('estop'))
        self.btn_home.clicked.connect(lambda: self._emit_drive('home'))

    def _emit_drive(self, cmd):
        payload = {'cmd': cmd, 'motor_speed': self.motor_slider.value(), 'servo': self.servo_slider.value(), 'ts': time.time()}
        self.drive_command.emit(payload)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Rover Controller - NASA GUI Inspired')
        self.resize(1400, 850)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(6,6,6,6)

        # Left: camera + map area
        left_frame = QtWidgets.QFrame()
        left_layout = QtWidgets.QVBoxLayout(left_frame)

        # Top row: two camera feeds side by side
        cam_row = QtWidgets.QHBoxLayout()
        self.cam1 = VideoWidget('Cam A')
        self.cam2 = VideoWidget('Cam B')
        cam_row.addWidget(self.cam1)
        cam_row.addWidget(self.cam2)
        left_layout.addLayout(cam_row)

        # Middle: large map / scene
        self.map_widget = VideoWidget('Map / Scene')
        # if MAP_IMAGE exists, show it
        if os.path.exists(MAP_IMAGE):
            img = cv2.imread(MAP_IMAGE)
            if img is not None:
                self.map_widget.set_frame(img)
        left_layout.addWidget(self.map_widget)

        # bottom timeline and indicators
        bottom = QtWidgets.QHBoxLayout()
        self.play_btn = QtWidgets.QPushButton('Play')
        self.pause_btn = QtWidgets.QPushButton('Pause')
        self.timeline = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.timeline.setRange(0,1000)
        self.time_lbl = QtWidgets.QLabel('00:00 / 00:00')
        bottom.addWidget(self.play_btn)
        bottom.addWidget(self.pause_btn)
        bottom.addWidget(self.timeline, 1)
        bottom.addWidget(self.time_lbl)
        left_layout.addLayout(bottom)

        main_layout.addWidget(left_frame, 3)

        # Right: controls + telemetry + logs
        right_frame = QtWidgets.QFrame()
        right_layout = QtWidgets.QVBoxLayout(right_frame)

        # control panel
        self.controls = ControlPanel()
        right_layout.addWidget(self.controls)

        # telemetry panel
        gb_tel = QtWidgets.QGroupBox('Telemetry')
        tel_layout = QtWidgets.QFormLayout()
        self.lbl_battery = QtWidgets.QLabel('100%')
        self.lbl_speed = QtWidgets.QLabel('0.00 m/s')
        self.lbl_dist = QtWidgets.QLabel('0.00 m')
        self.lbl_gps = QtWidgets.QLabel('N/A')
        tel_layout.addRow('Battery:', self.lbl_battery)
        tel_layout.addRow('Speed:', self.lbl_speed)
        tel_layout.addRow('Distance:', self.lbl_dist)
        tel_layout.addRow('GPS:', self.lbl_gps)
        gb_tel.setLayout(tel_layout)
        right_layout.addWidget(gb_tel)

        # sensor list
        gb_sensors = QtWidgets.QGroupBox('Sensors')
        v = QtWidgets.QVBoxLayout()
        self.sensor_list = QtWidgets.QListWidget()
        v.addWidget(self.sensor_list)
        gb_sensors.setLayout(v)
        right_layout.addWidget(gb_sensors)

        # logs
        gb_logs = QtWidgets.QGroupBox('Logs')
        v2 = QtWidgets.QVBoxLayout()
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        v2.addWidget(self.log_text)
        gb_logs.setLayout(v2)
        right_layout.addWidget(gb_logs, 1)

        main_layout.addWidget(right_frame, 1)

        # Video threads (simulate two camera sources)
        self.threads = []
        self.threads.append(VideoThread('Cam A', 0))  # default webcam
        self.threads.append(VideoThread('Cam B', 0))  # same webcam by default
        for t in self.threads:
            t.frame_ready.connect(self.on_frame)
            t.start()

        # telemetry simulator
        self.tele = TelemetrySimulator()
        self.tele.telemetry_updated.connect(self.on_telemetry)
        self.tele.start()

        # wiring control signals
        self.controls.drive_command.connect(self.on_drive_command)

        # timers for UI refresh / simulated indicators
        self._last_ts = time.time()
        self._log_counter = 0

        # play / pause wiring
        self.play_btn.clicked.connect(lambda: self.log('Playback: Play'))
        self.pause_btn.clicked.connect(lambda: self.log('Playback: Pause'))

        # close handling
        self._running = True

    def on_frame(self, name, frame):
        # route frames by name
        if name == 'Cam A':
            self.cam1.set_frame(frame)
        elif name == 'Cam B':
            self.cam2.set_frame(frame)
        else:
            self.map_widget.set_frame(frame)

    def on_telemetry(self, payload):
        # update labels and widgets
        self.lbl_battery.setText(f"{payload['battery']} %")
        self.lbl_speed.setText(f"{payload['speed']} m/s")
        self.lbl_dist.setText(f"{payload['distance']} m")
        self.lbl_gps.setText(f"{payload['gps'][0]:.5f}, {payload['gps'][1]:.5f}")
        self.controls.batt.setValue(int(payload['battery']))
        # update sensor list
        self.sensor_list.clear()
        self.sensor_list.addItem(f"Temp: {payload['temp']} C")
        self.sensor_list.addItem(f"Battery: {payload['battery']} %")
        self.sensor_list.addItem(f"Speed: {payload['speed']} m/s")

    def on_drive_command(self, payload):
        # log and display
        cmd = payload.get('cmd')
        self.log(f"Drive cmd: {cmd} | motor:{payload.get('motor_speed')} servo:{payload.get('servo')}")
        # Here: send the payload to real rover via ROS / serial / websocket
        # Example (ROS pseudocode):
        # ros_pub.publish(Twist(...) or a custom message)

    def log(self, text):
        ts = time.strftime('%H:%M:%S')
        self.log_text.appendPlainText(f"[{ts}] {text}")
        # keep log auto-scrolled
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def closeEvent(self, event):
        # stop threads and telemetry
        for t in self.threads:
            try:
                t.stop()
            except Exception:
                pass
        self.tele.stop()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
