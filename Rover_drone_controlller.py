import cv2
import random
import threading
from PyQt5 import QtCore, QtWidgets, QtGui


class FPVController(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # --------- Build Layout ---------
        self.setWindowTitle("FPV Drone & Rover Controller")
        layout = QtWidgets.QVBoxLayout(self)

        # -------- Split upper and lower sections --------
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        layout.addWidget(self.splitter)

        # -------- Upper: Video + Right Panel --------
        upper_widget = QtWidgets.QWidget()
        upper_layout = QtWidgets.QHBoxLayout(upper_widget)

        # Left: Video Stream
        self.video_label = QtWidgets.QLabel("Video Stream")
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: lime; font-size: 16px;")
        upper_layout.addWidget(self.video_label, 2)

        # Right: Telemetry + Controls
        right_panel = QtWidgets.QVBoxLayout()

        self.telemetry_text = QtWidgets.QTextEdit()
        self.telemetry_text.setReadOnly(True)
        self.telemetry_text.setStyleSheet(
            "background-color: black; color: #39ff14; font-family: Consolas; font-size: 14px;"
        )
        right_panel.addWidget(self.telemetry_text, 3)

        # Servo + speed sliders
        sliders_layout = QtWidgets.QHBoxLayout()
        self.servo_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.servo_slider.setRange(0, 180)
        self.servo_slider.setValue(90)
        sliders_layout.addWidget(QtWidgets.QLabel("Servo"))
        sliders_layout.addWidget(self.servo_slider)

        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.speed_slider.setRange(0, 255)
        self.speed_slider.setValue(100)
        sliders_layout.addWidget(QtWidgets.QLabel("Speed"))
        sliders_layout.addWidget(self.speed_slider)

        right_panel.addLayout(sliders_layout)

        # Rover control buttons
        rover_controls = QtWidgets.QGridLayout()
        self.btn_forward = QtWidgets.QPushButton("↑ Forward")
        self.btn_backward = QtWidgets.QPushButton("↓ Backward")
        self.btn_left = QtWidgets.QPushButton("← Left")
        self.btn_right = QtWidgets.QPushButton("→ Right")
        self.btn_stop = QtWidgets.QPushButton("■ Stop")

        rover_controls.addWidget(self.btn_forward, 0, 1)
        rover_controls.addWidget(self.btn_left, 1, 0)
        rover_controls.addWidget(self.btn_stop, 1, 1)
        rover_controls.addWidget(self.btn_right, 1, 2)
        rover_controls.addWidget(self.btn_backward, 2, 1)

        right_panel.addLayout(rover_controls)

        # Target lock + Shoot buttons
        action_layout = QtWidgets.QHBoxLayout()
        self.lock_btn = QtWidgets.QPushButton("Lock Target")
        self.shoot_btn = QtWidgets.QPushButton("Shoot")
        action_layout.addWidget(self.lock_btn)
        action_layout.addWidget(self.shoot_btn)
        right_panel.addLayout(action_layout)

        upper_layout.addLayout(right_panel, 2)
        self.splitter.addWidget(upper_widget)

        # -------- Lower: Logs --------
        lower_widget = QtWidgets.QWidget()
        lower_layout = QtWidgets.QVBoxLayout(lower_widget)

        self.log_area = QtWidgets.QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(
            "background-color: black; color: cyan; font-family: Consolas; font-size: 13px;"
        )
        lower_layout.addWidget(self.log_area, 3)

        # Log control buttons
        log_buttons = QtWidgets.QHBoxLayout()
        self.clear_log_btn = QtWidgets.QPushButton("Clear Logs")
        self.save_log_btn = QtWidgets.QPushButton("Save Logs")
        self.reload_btn = QtWidgets.QPushButton("Reload Rover")
        log_buttons.addWidget(self.clear_log_btn)
        log_buttons.addWidget(self.save_log_btn)
        log_buttons.addWidget(self.reload_btn)
        lower_layout.addLayout(log_buttons)

        self.splitter.addWidget(lower_widget)

        # -------- Internal States --------
        self.cap = None
        self._video_thread = None
        self._running = False

        # -------- Telemetry simulation --------
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._simulate_telemetry)

        # -------- Connect button actions --------
        self.btn_forward.clicked.connect(lambda: self._log("[CMD] Forward"))
        self.btn_backward.clicked.connect(lambda: self._log("[CMD] Backward"))
        self.btn_left.clicked.connect(lambda: self._log("[CMD] Left"))
        self.btn_right.clicked.connect(lambda: self._log("[CMD] Right"))
        self.btn_stop.clicked.connect(lambda: self._log("[CMD] Stop"))
        self.lock_btn.clicked.connect(lambda: self._log("[ACTION] Target Locked"))
        self.shoot_btn.clicked.connect(lambda: self._log("[ACTION] Shoot Activated"))
        self.clear_log_btn.clicked.connect(lambda: self.log_area.clear())
        self.save_log_btn.clicked.connect(self._save_logs)
        self.reload_btn.clicked.connect(lambda: self._log("[SYSTEM] Rover Reloaded"))

    # ---------------- FPV activate ----------------
    def activate(self):
        if not self._running:
            self._running = True
            self.timer.start(1000)  # telemetry update
            self._start_video_thread()
            self._log(">>> FPV Controller Activated <<<")

    def deactivate(self):
        """Stop FPV when leaving tab"""
        self._running = False
        self.timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.video_label.setText("Video Stream")
        self._log(">>> FPV Controller Deactivated <<<")

    # ---------------- Video thread ----------------
    def _start_video_thread(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # safer on Windows

        def run():
            while self._running and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    continue
                frame = cv2.resize(frame, (640, 360))
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(qimg)
                self.video_label.setPixmap(pixmap)

        self._video_thread = threading.Thread(target=run, daemon=True)
        self._video_thread.start()

    # ---------------- Fake Telemetry ----------------
    def _simulate_telemetry(self):
        battery = random.uniform(50, 100)
        speed = self.speed_slider.value() / 10.0
        servo = self.servo_slider.value()
        altitude = random.uniform(5, 15)
        distance = random.uniform(100, 500)

        self._log(
            f"[Telemetry] Bat:{battery:.1f}% | Speed:{speed:.1f} m/s | Servo:{servo}° | Alt:{altitude:.1f} m | Dist:{distance:.1f} m"
        )

    # ---------------- Logger ----------------
    def _log(self, text):
        self.log_area.append(f"<span style='color:#39ff14;'>{text}</span>")
        self.telemetry_text.append(f"<span style='color:cyan;'>{text}</span>")

    # ---------------- Save Logs ----------------
    def _save_logs(self):
        with open("fpv_logs.txt", "w") as f:
            f.write(self.log_area.toPlainText())
        self._log("[SYSTEM] Logs saved to fpv_logs.txt")

    # ---------------- Cleanup ----------------
    def closeEvent(self, ev):
        self.deactivate()
        ev.accept()
