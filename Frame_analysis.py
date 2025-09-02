import cv2
import threading
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWebEngineWidgets import QWebEngineView
import folium
import io


class MultiViewModule(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        # Split video feeds and map
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        # ---------------- Left: Multi-View Feeds ----------------
        video_widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(video_widget)

        self.video_labels = []
        titles = ["Rover Front Cam", "Rover Rear Cam", "Drone Cam"]

        for i, title in enumerate(titles):
            lbl = QtWidgets.QLabel(title)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl.setStyleSheet("background-color: black; color: white; font-size: 14px;")
            lbl.setMinimumSize(300, 200)
            grid.addWidget(lbl, i // 2, i % 2)  # place in grid
            self.video_labels.append(lbl)

        splitter.addWidget(video_widget)

        # ---------------- Right: Embedded Map ----------------
        self.map_view = QWebEngineView()
        self._load_map()
        splitter.addWidget(self.map_view)

        # Capture threads
        self.captures = []
        self.running = False

    def _load_map(self):
        # Simple folium map
        m = folium.Map(location=[28.6139, 77.2090], zoom_start=12)  # Delhi coords as demo
        folium.Marker([28.6139, 77.2090], popup="Rover Location").add_to(m)

        data = io.BytesIO()
        m.save(data, close_file=False)
        self.map_view.setHtml(data.getvalue().decode())

    # ---------------- Video Capture ----------------
    def start_capture(self):
        if self.running:
            return
        self.running = True

        # Replace with actual streams for rover/drone
        sources = [0, 0, 0]  # using laptop cam for demo (all same)

        self.captures = []
        for i, src in enumerate(sources):
            cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
            self.captures.append(cap)

            thread = threading.Thread(target=self._update_frame, args=(cap, self.video_labels[i]))
            thread.daemon = True
            thread.start()

    def stop_capture(self):
        self.running = False
        for cap in self.captures:
            if cap.isOpened():
                cap.release()
        self.captures = []

    def _update_frame(self, cap, label):
        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                frame = cv2.resize(frame, (320, 240))
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(qimg)
                label.setPixmap(pixmap)
        label.clear()
        label.setText("No Signal")
