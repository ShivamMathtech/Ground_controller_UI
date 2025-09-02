"""
gcs_fullscreen_horizontal.py
Professional Rover GCS - horizontal split layout
Upper half: Map (left) + Two cameras (right, stacked)
Lower half: Telemetry | Controls | Neon Log area

Run:
 pip install PyQt5 PyQtWebEngine folium opencv-python numpy
 python gcs_fullscreen_horizontal.py
"""

import sys
import os
import time
import math
import threading
import folium
import cv2
import numpy as np

from PyQt5 import QtCore, QtGui, QtWidgets
from Analiysis import AnalysisModule
from Rover_drone_controlller import FPVController
from  Frame_analysis import MultiViewModule
# Try import QtWebEngineWidgets, fallback to opening map in browser
try:
    from PyQt5 import QtWebEngineWidgets
    WEBENGINE_AVAILABLE = True
except Exception:
    WEBENGINE_AVAILABLE = False
    import webbrowser

# ----------------------------
# Helper: Generate Folium map + JS (safe braces)
# ----------------------------
def generate_folium_map(lat=28.6, lon=77.2, fname="rover_map.html"):
    m = folium.Map(location=[lat, lon], zoom_start=16)
    folium.Marker([lat, lon], popup="Rover", icon=folium.Icon(color="red")).add_to(m)
    m.save(fname)

    # Append JS for updateRover and path; escape JS braces by doubling where needed
    js = """
<script>
    var roverMarker = L.marker([{lat}, {lon}]).addTo(map).bindPopup("Rover");
    var roverPath = L.polyline([[{lat}, {lon}]], {{color: 'blue'}}).addTo(map);

    function updateRover(lat, lon, locked) {{
        roverMarker.setLatLng([lat, lon]);
        roverPath.addLatLng([lat, lon]);
        if (locked) {{
            // change marker icon to green when locked
            roverMarker.setIcon(L.icon({{
                iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x-green.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
            }}));
        }} else {{
            roverMarker.setIcon(L.icon({{
                iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
            }}));
        }}
    }}
</script>
""".format(lat=lat, lon=lon)

    with open(fname, "a", encoding="utf-8") as f:
        f.write(js)
    return fname

# ----------------------------
# Map Widget (Folium + QWebEngine or fallback)
# ----------------------------
class MapWidget(QtWidgets.QWidget):
    def __init__(self, lat=28.6, lon=77.2, parent=None):
        super().__init__(parent)
        self.lat = lat
        self.lon = lon
        self.locked = False
        self.mapfile = generate_folium_map(lat, lon, fname="rover_map.html")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        if WEBENGINE_AVAILABLE:
            self.view = QtWebEngineWidgets.QWebEngineView()
            self.view.load(QtCore.QUrl.fromLocalFile(os.path.abspath(self.mapfile)))
            layout.addWidget(self.view)
        else:
            # fallback: show label and open map in default browser
            label = QtWidgets.QLabel("Map preview unavailable (PyQtWebEngine not installed). Map will open in browser.")
            label.setWordWrap(True)
            layout.addWidget(label)
            webbrowser.open('file://' + os.path.abspath(self.mapfile))

    def update_position(self, lat, lon):
        self.lat = lat
        self.lon = lon
        if WEBENGINE_AVAILABLE:
            # pass locked flag (1 or 0)
            js = f"updateRover({lat}, {lon}, {1 if self.locked else 0});"
            self.view.page().runJavaScript(js)

    def set_locked(self, locked: bool):
        self.locked = bool(locked)
        # update marker color immediately
        self.update_position(self.lat, self.lon)

# ----------------------------
# Video (camera) widget w/ fixed frame and fullscreen
# ----------------------------
video_link ="G:/GCS/vid.mp4"
class CameraWidget(QtWidgets.QWidget):
    def __init__(self, cam_source=video_link, title="Camera", fixed_size=(480,270), parent=None):
        super().__init__(parent)
        self.cam_source = video_link
        self.fixed_w, self.fixed_h = fixed_size
        self.fullscreen_window = None
        print(self.cam_source)
        layout = QtWidgets.QVBoxLayout(self)
        hdr = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(title)
        lbl.setStyleSheet("font-weight:bold;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        self.btn_full = QtWidgets.QPushButton("Full")
        self.btn_full.setToolTip("Open fullscreen")
        self.btn_full.clicked.connect(self.open_fullscreen)
        hdr.addWidget(self.btn_full)
        layout.addLayout(hdr)

        self.video_label = QtWidgets.QLabel()
        self.video_label.setFixedSize(self.fixed_w, self.fixed_h)
        self.video_label.setStyleSheet("background-color: black; border: 2px solid #444;")
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.video_label, alignment=QtCore.Qt.AlignCenter)

        # Try open camera
        try:
            self.cap = cv2.VideoCapture(self.cam_source)
            if not self.cap.isOpened():
                raise RuntimeError("Camera not opened")
            self.using_camera = True
        except Exception:
            self.cap = None
            self.using_camera = False
            # set placeholder image
            placeholder = QtGui.QPixmap(self.fixed_w, self.fixed_h)
            placeholder.fill(QtGui.QColor("#111"))
            painter = QtGui.QPainter(placeholder)
            painter.setPen(QtGui.QPen(QtGui.QColor("#aaa")))
            painter.setFont(QtGui.QFont("Sans", 12))
            painter.drawText(placeholder.rect(), QtCore.Qt.AlignCenter, "No camera\nsource")
            painter.end()
            self.video_label.setPixmap(placeholder)

        # start timer update
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._update)
        self.timer.start(30)

    def _update(self):
        if not self.using_camera or self.cap is None:
            return
        ret, frame = self.cap.read()
        if not ret:
            return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        qimg = QtGui.QImage(frame.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)
        # scale to fixed size but do not stretch (keep aspect, letterbox)
        scaled = pix.scaled(self.fixed_w, self.fixed_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        # To maintain fixed frame size, create a black canvas and center scaled image
        canvas = QtGui.QPixmap(self.fixed_w, self.fixed_h)
        canvas.fill(QtGui.QColor("black"))
        painter = QtGui.QPainter(canvas)
        x = (self.fixed_w - scaled.width()) // 2
        y = (self.fixed_h - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
        self.video_label.setPixmap(canvas)
        # if fullscreen open, update that too
        if self.fullscreen_window:
            fs_pix = pix.scaled(self.fullscreen_window.width(), self.fullscreen_window.height(),
                                QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.fullscreen_window.setPixmap(fs_pix)

    def open_fullscreen(self):
        if self.fullscreen_window:
            return
        self.fullscreen_window = FullscreenWindow()
        self.fullscreen_window.closed.connect(self._on_fullscreen_closed)
        self.fullscreen_window.showFullScreen()

    def _on_fullscreen_closed(self):
        self.fullscreen_window = None

    def close(self):
        if self.cap:
            self.cap.release()
        super().close()

class FullscreenWindow(QtWidgets.QLabel):
    closed = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: black;")
        self.setAlignment(QtCore.Qt.AlignCenter)
    def keyPressEvent(self, ev):
        # allow Esc to close fullscreen
        if ev.key() == QtCore.Qt.Key_Escape:
            self.close()
    def closeEvent(self, ev):
        self.closed.emit()
        ev.accept()

# ----------------------------
# Telemetry Panel - half of lower area
# ----------------------------
class TelemetryPanel(QtWidgets.QGroupBox):
    def __init__(self):
        super().__init__("Telemetry & Status")
        self.setMinimumHeight(220)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        # left column labels
        labels = ["Battery (%)", "Speed (m/s)", "Distance (m)", "GPS Lat", "GPS Lon", "Temp (°C)"]
        self.values = {}
        for i, key in enumerate(labels):
            lbl = QtWidgets.QLabel(key + ":")
            val = QtWidgets.QLabel("—")
            val.setStyleSheet("font-weight:bold;")
            layout.addWidget(lbl, i, 0, alignment=QtCore.Qt.AlignLeft)
            layout.addWidget(val, i, 1, alignment=QtCore.Qt.AlignLeft)
            self.values[key] = val

        # small progress bar for battery
        self.batt_bar = QtWidgets.QProgressBar()
        self.batt_bar.setRange(0,100)
        self.batt_bar.setValue(100)
        layout.addWidget(QtWidgets.QLabel("Battery Level"), 0, 2)
        layout.addWidget(self.batt_bar, 0, 3)

        # long status / small sensors area
        self.small_status = QtWidgets.QTextEdit()
        self.small_status.setReadOnly(True)
        self.small_status.setFixedHeight(80)
        self.small_status.setStyleSheet("background:#111; color:#ddd;")
        layout.addWidget(QtWidgets.QLabel("Sensors / Quick Status"), 4, 2)
        layout.addWidget(self.small_status, 5, 2, 1, 2)

    def update(self, telemetry_dict):
        # telemetry_dict expected keys: battery, speed, distance, lat, lon, temp
        self.values["Battery (%)"].setText(f"{telemetry_dict.get('battery', 0)}")
        self.values["Speed (m/s)"].setText(f"{telemetry_dict.get('speed', 0):.2f}")
        self.values["Distance (m)"].setText(f"{telemetry_dict.get('distance', 0):.1f}")
        self.values["GPS Lat"].setText(f"{telemetry_dict.get('lat', 0):.6f}")
        self.values["GPS Lon"].setText(f"{telemetry_dict.get('lon', 0):.6f}")
        self.values["Temp (°C)"].setText(f"{telemetry_dict.get('temp', 0):.1f}")
        self.batt_bar.setValue(int(telemetry_dict.get('battery', 0)))
        # append small status
        s = f"Last update: {time.strftime('%H:%M:%S')} | Battery {telemetry_dict.get('battery',0)}%"
        self.small_status.append(s)

# ----------------------------
# Control Panel - center lower area
# ----------------------------
class ControlPanel(QtWidgets.QGroupBox):
    def __init__(self):
        super().__init__("Rover Controls")
        self.setMinimumHeight(220)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        # Movement pad (buttons)
        self.btn_fwd = QtWidgets.QPushButton("▲")
        self.btn_back = QtWidgets.QPushButton("▼")
        self.btn_left = QtWidgets.QPushButton("◀")
        self.btn_right = QtWidgets.QPushButton("▶")
        self.btn_circle = QtWidgets.QPushButton("◎")

        for b in [self.btn_fwd, self.btn_back, self.btn_left, self.btn_right, self.btn_circle]:
            b.setFixedSize(60,40)

        pad = QtWidgets.QGridLayout()
        pad.addWidget(self.btn_fwd, 0, 1)
        pad.addWidget(self.btn_left, 1, 0)
        pad.addWidget(self.btn_circle, 1, 1)
        pad.addWidget(self.btn_right, 1, 2)
        pad.addWidget(self.btn_back, 2, 1)
        layout.addLayout(pad, 0, 0, 2, 1)

        # Speed lever (slider)
        layout.addWidget(QtWidgets.QLabel("Speed Lever"), 0, 1)
        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.speed_slider.setRange(0, 255)
        self.speed_slider.setValue(150)
        layout.addWidget(self.speed_slider, 1, 1)

        # Servo lever (dial)
        layout.addWidget(QtWidgets.QLabel("Servo Angle"), 0, 2)
        self.servo_dial = QtWidgets.QDial()
        self.servo_dial.setRange(0, 180)
        self.servo_dial.setValue(90)
        self.servo_dial.setNotchesVisible(True)
        layout.addWidget(self.servo_dial, 1, 2)

        # Camera mount pan/tilt (two sliders)
        layout.addWidget(QtWidgets.QLabel("Cam Mount Pan"), 2, 0)
        self.pan_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.pan_slider.setRange(-90,90)
        self.pan_slider.setValue(0)
        layout.addWidget(self.pan_slider, 3, 0)

        layout.addWidget(QtWidgets.QLabel("Cam Mount Tilt"), 2, 1)
        self.tilt_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.tilt_slider.setRange(-45,45)
        self.tilt_slider.setValue(0)
        layout.addWidget(self.tilt_slider, 3, 1)

        # Lock target and shoot
        self.lock_btn = QtWidgets.QPushButton("Lock Target")
        self.lock_btn.setCheckable(True)
        self.shoot_btn = QtWidgets.QPushButton("ACTIVATE SHOOT")
        self.shoot_btn.setStyleSheet("background-color: darkred; color:white; font-weight:bold;")
        layout.addWidget(self.lock_btn, 2, 2)
        layout.addWidget(self.shoot_btn, 3, 2)

# ----------------------------
# Log / Terminal Widget (neon)
# ----------------------------
class LogWidget(QtWidgets.QGroupBox):
    def __init__(self):
        super().__init__("Mission Log")
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.terminal = QtWidgets.QPlainTextEdit()
        self.terminal.setReadOnly(True)
        # neon terminal styling
        self.terminal.setStyleSheet("""
            background: #000;
            color: #39ff14;  /* neon green */
            font-family: 'Courier New', monospace;
            font-size: 12px;
        """)
        layout.addWidget(self.terminal)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Save Log")
        self.btn_clear = QtWidgets.QPushButton("Clear Log")
        self.btn_reload = QtWidgets.QPushButton("Reload Rover")
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_reload)
        layout.addLayout(btn_row)

        # signals will be connected from main window

    def log(self, text):
        ts = time.strftime("%H:%M:%S")
        self.terminal.appendPlainText(f"[{ts}] {text}")

    def save_log(self, path=None):
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Log", "mission_log.txt", "Text Files (*.txt)")
            if not path:
                return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.terminal.toPlainText())
        self.log(f"Log saved to {path}")

    def clear(self):
        self.terminal.clear()
        self.log("Log cleared")

# ----------------------------
# Main Window assembling everything
# ----------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ABHIMANYU ROVER CONTROLLER SYSTEM")
        self.resize(1400, 700)

        # QTabWidget will be the central widget
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # ----------------- Tab 1: Ground Control -----------------
        rover_tab = QtWidgets.QWidget()
        self.fpv_controller = FPVController()

        main_v = QtWidgets.QVBoxLayout(rover_tab)
        main_v.setContentsMargins(6, 6, 6, 6)
        main_v.setSpacing(6)

        # UPPER HALF: Map + Cameras
        upper = QtWidgets.QWidget()
        upper_layout = QtWidgets.QHBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(6)

        self.map_widget = MapWidget(lat=28.60000, lon=77.20000)

        cams_widget = QtWidgets.QWidget()
        cams_v = QtWidgets.QVBoxLayout(cams_widget)
        cams_v.setContentsMargins(0, 0, 0, 0)
        self.cam_top = CameraWidget(cam_source=0, title="Front Camera", fixed_size=(560, 320))
        self.cam_bottom = CameraWidget(cam_source=1, title="Rear Camera", fixed_size=(560, 320))
        cams_v.addWidget(self.cam_top)
        cams_v.addWidget(self.cam_bottom)

        upper_layout.addWidget(self.map_widget, 3)
        upper_layout.addWidget(cams_widget, 2)
        main_v.addWidget(upper, 3)

        # LOWER HALF: Telemetry | Controls | Log
        lower = QtWidgets.QWidget()
        lower_layout = QtWidgets.QHBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(6)

        self.telemetry = TelemetryPanel()
        self.controls = ControlPanel()
        self.log_widget = LogWidget()

        lower_layout.addWidget(self.telemetry, 2)
        lower_layout.addWidget(self.controls, 2)
        lower_layout.addWidget(self.log_widget, 3)
        main_v.addWidget(lower, 1)

        # Add to tabs
        self.tabs.addTab(rover_tab, "Ground Control")

        # ----------------- Tab 2: Analysis -----------------
        self.analysis_tab = AnalysisModule()
        self.tabs.addTab(self.analysis_tab, "Telemetry Analysis")
        #--------------------Tab 3: FPV Controlller-----------
        self.tabs.addTab(self.fpv_controller, "FPV Controller")
         # Connect tab change
        self.tabs.currentChanged.connect(self.on_tab_change)

        
        #------------------ Tab 4: Fame Anaylisis -----------
        self.multi_view = MultiViewModule()
        self.tabs.addTab(self.multi_view, "Multi-View")
        # ----------------- Connect signals -----------------
      
        self.controls.btn_fwd.pressed.connect(lambda: self._cmd("MOVE_FORWARD"))
        self.controls.btn_back.pressed.connect(lambda: self._cmd("MOVE_BACK"))
        self.controls.btn_left.pressed.connect(lambda: self._cmd("TURN_LEFT"))
        self.controls.btn_right.pressed.connect(lambda: self._cmd("TURN_RIGHT"))
        self.controls.btn_circle.pressed.connect(lambda: self._cmd("CIRCULAR_MOTION"))
        self.controls.speed_slider.valueChanged.connect(lambda v: self._cmd(f"SPEED:{v}"))
        self.controls.servo_dial.valueChanged.connect(lambda v: self._cmd(f"SERVO:{v}"))
        self.controls.pan_slider.valueChanged.connect(lambda v: self._cmd(f"PAN:{v}"))
        self.controls.tilt_slider.valueChanged.connect(lambda v: self._cmd(f"TILT:{v}"))
        self.controls.lock_btn.toggled.connect(self._toggle_lock)
        self.controls.shoot_btn.clicked.connect(self._activate_shoot)

        self.log_widget.btn_save.clicked.connect(self.log_widget.save_log)
        self.log_widget.btn_clear.clicked.connect(self.log_widget.clear)
        self.log_widget.btn_reload.clicked.connect(self._reload_rover)

        # ----------------- Telemetry Simulation -----------------
        self._sim_lat = 28.6
        self._sim_lon = 77.2
        self._sim_distance = 0.0
        self._sim_battery = 100.0
        self._sim_speed = 0.0
        self._sim_temp = 25.0

        self.sim_timer = QtCore.QTimer()
        self.sim_timer.timeout.connect(self._simulate_telemetry)
        self.sim_timer.start(1500)

        # Initial logs
        self.log_widget.log("GCS Started")
        self.log_widget.log("Map & cameras initialized")
    #--------------- Tab Switching For Camera Controller--------------------
    def on_tab_change(self, index):
        # Get widget at this tab index
        widget = self.tabs.widget(index)
        # If FPV tab selected -> start video
        if widget == self.fpv_controller:
          self.fpv_controller.activate()
        else:
          self.fpv_controller.deactivate()
        if widget == self.multi_view:
          self.multi_view.start_capture()
        else:
         self.multi_view.stop_capture()  
    # ---------------- command handlers ----------------
    def _cmd(self, cmd_text):
        self.log_widget.log(f"CMD -> {cmd_text}")

    def _toggle_lock(self, checked):
        self.map_widget.set_locked(checked)
        self.log_widget.log("Target Locked" if checked else "Target Unlocked")

    def _activate_shoot(self):
        self.log_widget.log(">>> SHOOT ACTIVATED <<<")
        self.log_widget.log("Projectile fired at target coordinates")

    def _reload_rover(self):
        self._sim_lat, self._sim_lon = 28.6, 77.2
        self._sim_distance = 0.0
        self._sim_battery = 100.0
        self._sim_speed = 0.0
        self.log_widget.log("Rover reloaded / reset to home position")
        self.map_widget.update_position(self._sim_lat, self._sim_lon)

    # ---------------- telemetry simulation ----------------
    def _simulate_telemetry(self):
        step = (self.controls.speed_slider.value() / 255.0) * 0.0004
        self._sim_lat += step + (np.random.randn() * 1e-6)
        self._sim_lon += step + (np.random.randn() * 1e-6)
        self._sim_distance += (step * 111000)
        self._sim_speed = (self.controls.speed_slider.value() / 255.0) * 1.5
        self._sim_battery = max(0.0, self._sim_battery - (self._sim_speed * 0.02) - 0.05)
        self._sim_temp = 20 + np.random.randn() * 0.5

        telemetry = {
            "battery": round(self._sim_battery, 1),
            "speed": round(self._sim_speed, 2),
            "distance": round(self._sim_distance, 1),
            "lat": self._sim_lat,
            "lon": self._sim_lon,
            "temp": round(self._sim_temp, 1)
        }
        self.telemetry.update(telemetry)
        self.map_widget.update_position(self._sim_lat, self._sim_lon)
        self.log_widget.log(f"Telemetry update | Bat:{telemetry['battery']}% Speed:{telemetry['speed']}m/s Dist:{telemetry['distance']}m")

    def closeEvent(self, ev):
        try: self.cam_top.cap.release()
        except Exception: pass
        try: self.cam_bottom.cap.release()
        except Exception: pass
        ev.accept()


# ----------------------------
# Run the app
# ----------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
