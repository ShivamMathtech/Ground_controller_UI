# mission_planner.py
import os
import random
import tempfile
import requests
from PyQt5 import QtCore, QtWidgets, QtWebEngineWidgets
import folium


class MissionPlanner(QtWidgets.QWidget):
    """ Mission Planner module with interactive Folium map + ORS directions """

    mission_uploaded = QtCore.pyqtSignal(list)  # emits list of waypoints

    def __init__(self, ORS_KEY=None, parent=None):
        super().__init__(parent)

        self.ORS_KEY = ORS_KEY
        self.waypoints = []

        layout = QtWidgets.QVBoxLayout(self)

        # ---------- Top: Folium Map ----------
        self.map_path = os.path.join(tempfile.gettempdir(), "mission_map.html")
        self._generate_map()

        self.web_view = QtWebEngineWidgets.QWebEngineView()
        self.web_view.setUrl(QtCore.QUrl.fromLocalFile(self.map_path))
        layout.addWidget(self.web_view, 3)

        # ---------- Middle: Waypoints ----------
        wp_group = QtWidgets.QGroupBox("Waypoints")
        wp_layout = QtWidgets.QVBoxLayout(wp_group)

        self.wp_list = QtWidgets.QListWidget()
        wp_layout.addWidget(self.wp_list)

        btns = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("➕ Add WP")
        self.btn_remove = QtWidgets.QPushButton("🗑 Remove WP")
        self.btn_clear = QtWidgets.QPushButton("❌ Clear All")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_remove)
        btns.addWidget(self.btn_clear)
        wp_layout.addLayout(btns)

        layout.addWidget(wp_group, 2)

        # ---------- Bottom: Mission Controls ----------
        control_group = QtWidgets.QGroupBox("Mission Controls")
        ctrl_layout = QtWidgets.QHBoxLayout(control_group)

        self.btn_upload = QtWidgets.QPushButton("⬆ Upload Mission")
        self.btn_start = QtWidgets.QPushButton("▶ Start Mission")
        self.btn_pause = QtWidgets.QPushButton("⏸ Pause")
        self.btn_resume = QtWidgets.QPushButton("⏯ Resume")
        self.btn_abort = QtWidgets.QPushButton("⛔ Abort")

        for b in [self.btn_upload, self.btn_start, self.btn_pause, self.btn_resume, self.btn_abort]:
            ctrl_layout.addWidget(b)

        layout.addWidget(control_group, 1)

        # ---------- Status / Log ----------
        self.log_area = QtWidgets.QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: black; color: cyan; font-family: Consolas;")
        layout.addWidget(self.log_area, 1)

        # ---------- Connections ----------
        self.btn_add.clicked.connect(self._add_waypoint)
        self.btn_remove.clicked.connect(self._remove_waypoint)
        self.btn_clear.clicked.connect(self._clear_waypoints)
        self.btn_upload.clicked.connect(self._upload_mission)

        self.btn_start.clicked.connect(lambda: self._log("[MISSION] Started"))
        self.btn_pause.clicked.connect(lambda: self._log("[MISSION] Paused"))
        self.btn_resume.clicked.connect(lambda: self._log("[MISSION] Resumed"))
        self.btn_abort.clicked.connect(lambda: self._log("[MISSION] Aborted"))

    # ---------------- Map Functions ----------------
    def _generate_map(self):
        """Generate initial map or update with waypoints"""
        m = folium.Map(location=[28.61, 77.23], zoom_start=13)

        # Draw markers
        for i, wp in enumerate(self.waypoints, start=1):
            folium.Marker(wp, popup=f"WP {i}", tooltip=f"Waypoint {i}",
                          icon=folium.Icon(color="blue", icon="flag")).add_to(m)

        # Draw path using ORS if key is available
        if len(self.waypoints) > 1 and self.ORS_KEY:
            try:
                coords = [[lon, lat] for lat, lon in self.waypoints]  # ORS requires [lon,lat]
                resp = requests.post(
                    "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
                    headers={"Authorization": self.ORS_KEY, "Content-Type": "application/json"},
                    json={"coordinates": coords}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    route_coords = [(lat, lon) for lon, lat in data["features"][0]["geometry"]["coordinates"]]
                    folium.PolyLine(route_coords, color="red", weight=3).add_to(m)
                    self._log("[ORS] Route added successfully")
                else:
                    self._log(f"[ORS ERROR] {resp.status_code}: {resp.text}")
            except Exception as e:
                self._log(f"[ORS Exception] {e}")

        elif len(self.waypoints) > 1:
            folium.PolyLine(self.waypoints, color="red", weight=2.5).add_to(m)

        m.save(self.map_path)

    def _refresh_map(self):
        self._generate_map()
        self.web_view.setUrl(QtCore.QUrl.fromLocalFile(self.map_path))

    # ---------------- Waypoint Functions ----------------
    def _add_waypoint(self):
        lat = round(random.uniform(28.60, 28.70), 6)
        lon = round(random.uniform(77.20, 77.30), 6)
        alt = random.randint(10, 100)
        wp_text = f"WP: {lat}, {lon}, Alt {alt}m"
        self.wp_list.addItem(wp_text)
        self.waypoints.append((lat, lon))
        self._log(f"[ADD] {wp_text}")
        self._refresh_map()

    def _remove_waypoint(self):
        row = self.wp_list.currentRow()
        if row >= 0:
            item = self.wp_list.takeItem(row)
            self._log(f"[REMOVE] {item.text()}")
            self.waypoints.pop(row)
            self._refresh_map()

    def _clear_waypoints(self):
        self.wp_list.clear()
        self.waypoints.clear()
        self._log("[CLEAR] All waypoints removed")
        self._refresh_map()

    def _upload_mission(self):
        waypoints = [self.wp_list.item(i).text() for i in range(self.wp_list.count())]
        if waypoints:
            self._log("[UPLOAD] Mission uploaded with waypoints:")
            for wp in waypoints:
                self._log(f"    {wp}")
            self.mission_uploaded.emit(waypoints)
        else:
            self._log("[UPLOAD] No waypoints to upload!")

    # ---------------- Logger ----------------
    def _log(self, msg):
        self.log_area.append(f"<span style='color:lime;'>{msg}</span>")
