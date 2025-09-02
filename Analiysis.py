from PyQt5 import QtCore, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np
import random

class AnalysisModule(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        # Create matplotlib figure
        self.figure, self.ax = plt.subplots(3, 1, figsize=(6, 8))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # Data buffers
        self.data = {
            "battery": [],
            "speed": [],
            "temp": [],
            "time": []
        }

        # Timer for simulating data updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)

    def update_data(self):
        t = len(self.data["time"]) + 1
        self.data["time"].append(t)
        self.data["battery"].append(max(0, 100 - t * 0.5 + random.uniform(-1, 1)))
        self.data["speed"].append(abs(random.gauss(1.5, 0.5)))
        self.data["temp"].append(20 + random.uniform(-2, 2))

        self.plot()

    def plot(self):
        self.ax[0].clear()
        self.ax[0].plot(self.data["time"], self.data["battery"], color="green")
        self.ax[0].set_title("Battery Life (%)")

        self.ax[1].clear()
        self.ax[1].plot(self.data["time"], self.data["speed"], color="blue")
        self.ax[1].set_title("Speed (m/s)")

        self.ax[2].clear()
        self.ax[2].plot(self.data["time"], self.data["temp"], color="red")
        self.ax[2].set_title("Temperature (°C)")

        self.canvas.draw()
