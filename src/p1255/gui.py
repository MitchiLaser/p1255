import sys
import random
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QFileDialog,
    QGridLayout,
)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator
import os
from p1255.p1255 import P1255
import ipaddress


class PlotWidget(FigureCanvas):
    def __init__(self):
        self.fig = Figure()
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
        

    def update_plot(self, dataset, voltage=True):
        self.ax.clear()
        
        
        if dataset:
            for channel in dataset.channels:
                if voltage:
                    self.ax.plot(channel.data, label=channel.name)
                    self.ax.set_ylabel('Voltage (V)')
                    self.ax.relim()
                    self.ax.autoscale_view()
                else:
                    self.ax.plot(channel.data_divisions, label=channel.name)
                    self.ax.yaxis.set_major_locator(MultipleLocator(1))
                    self.ax.set_ylim(-5,5)
            self.ax.legend()
        else:
            self.ax.text(0.5, 0.5, 'No Data', horizontalalignment='center', verticalalignment='center')
        self.ax.grid(True)
        self.draw()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("P1255 Oscilloscope GUI")
        self.plot_widget = PlotWidget()
        self.timer = None
        self.saving_directory = os.getcwd()

        self.init_ui()

        self.p1255 = P1255()
        self.current_dataset = None

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.voltage_mode = True

        # Plot
        layout.addWidget(self.plot_widget)

        # Controls
        controls = QGridLayout()

        # IP and Port
        controls.addWidget(QLabel("IP:"), 0, 0)
        self.ip_input = QLineEdit("172.23.167.73")
        controls.addWidget(self.ip_input, 0, 1)

        controls.addWidget(QLabel("Port:"), 0, 2)
        self.port_input = QLineEdit("3000")
        controls.addWidget(self.port_input, 0, 3)

        # Connect Button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_to_ip)
        controls.addWidget(self.connect_button, 0, 4)

        # Run and Capture Buttons
        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Continuously")
        self.run_button.setCheckable(True)
        self.run_button.clicked.connect(self.toggle_run)
        button_layout.addWidget(self.run_button)

        self.capture_button = QPushButton("Capture Single")
        self.capture_button.clicked.connect(self.capture_single)
        button_layout.addWidget(self.capture_button)

        self.save_button = QPushButton("Save Data")
        self.save_button.clicked.connect(self.save_data)
        button_layout.addWidget(self.save_button)
        
        self.mode_button = QPushButton("Toggle Voltage/Divisions")
        self.mode_button.setCheckable(True)
        self.mode_button.clicked.connect(self.toggle_voltage_mode)
        button_layout.addWidget(self.mode_button)

        controls.addLayout(button_layout, 1, 0, 1, 5)

        layout.addLayout(controls)

    def connect_to_ip(self):
        ip = self.ip_input.text()
        port = self.port_input.text()
        print(f"Connecting to {ip}:{port}...")
        self.p1255.connect(ipaddress.IPv4Address(ip), int(port))
        self.connect_button.setText("Connected")

    def toggle_run(self, checked):
        if checked:
            self.run_button.setText("Stop")
            self.start_updating()
        else:
            self.run_button.setText("Run Continuously")
            self.stop_updating()
            
    def toggle_voltage_mode(self):
        self.voltage_mode = not self.voltage_mode
        self.plot_widget.update_plot(self.current_dataset, self.voltage_mode)
        self.mode_button.setText("Show Divisions" if not self.voltage_mode else "Show Voltage")

    def start_updating(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.capture_single)
        self.timer.start(500)  # milliseconds

    def stop_updating(self):
        if self.timer:
            self.timer.stop()
            self.timer = None

    def capture_single(self):
        self.current_dataset = self.p1255.capture()
        self.plot_widget.update_plot(self.current_dataset, self.voltage_mode)

    def save_data(self):
        if not self.current_dataset:
            print("No data to save.")
            return

        filename = QFileDialog.getSaveFileName(
            self, "Save Data", self.saving_directory, "CSV Files (*.csv);;JSON Files (*.json);;Numpy Files (*.npy)"
        )[0]
        if not filename:
            return

        if filename.endswith('.csv'):
            self.current_dataset.save(filename, fmt='csv')
        elif filename.endswith('.json'):
            self.current_dataset.save(filename, fmt='json')
        elif filename.endswith('.npy'):
            self.current_dataset.save(filename, fmt='npy')
