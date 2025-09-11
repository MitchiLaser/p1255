from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFileDialog,
)
from PyQt5 import uic
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator
import matplotlib.pyplot as plt
import os
from p1255.p1255 import P1255
from p1255.constants import CONNECTION_HELP
import ipaddress
from PyQt5.QtWidgets import QMessageBox
from pathlib import Path
import yaml
import importlib.resources
import numpy as np


plt.style.use('dark_background')

ALIAS_FILE = Path().home() / ".p1255_ip_aliases.yaml"
COLORS = {
    "CH1": 'red',
    "CH2": 'yellow',
}


class PlotWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure()
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)

    def update_plot(self, dataset, unit, mode):
        """Update the plot with data and unit

        Parameters
        ----------
        dataset : Dataset
            The dataset to plot.
        unit : str
            The unit to plot ('Voltage' or 'Divisions').
        mode : str
            The mode of the oscilloscope ('Normal', 'X: Ch1, Y: Ch2', 'X: Ch2, Y: Ch1').
        """
        if unit not in ('Voltage', 'Divisions'):
            raise ValueError("Unit must be 'Voltage' or 'Divisions'")
        if mode not in ('Normal', 'X: Ch1, Y: Ch2', 'X: Ch2, Y: Ch1'):
            raise ValueError("Mode must be 'Normal', 'X: Ch1, Y: Ch2', or 'X: Ch2, Y: Ch1'")
        self.ax.clear()
        if dataset:
            if mode == 'Normal':
                time = np.linspace(start=(-1) * dataset.channels[0].timescale / 2, stop=dataset.channels[0].timescale / 2, num=len(dataset.channels[0].data), endpoint=True)
                if time[-1] < 1e-3:
                    time *= 1e6
                    self.ax.set_xlabel('Time (µs)')
                elif time[-1] < 1:
                    time *= 1e3
                    self.ax.set_xlabel('Time (ms)')
                else:
                    self.ax.set_xlabel('Time (s)')
                for i, channel in enumerate(dataset.channels):
                    if unit == 'Voltage':
                        self.ax.plot(time, channel.data, label=channel.name, color=COLORS[channel.name])
                        self.ax.set_ylabel('Voltage (V)')
                        self.ax.relim()
                        self.ax.autoscale_view()
                    else:  # Divisions
                        self.ax.plot(time, channel.data_divisions, label=channel.name, color=COLORS[channel.name])
                        self.ax.yaxis.set_major_locator(MultipleLocator(1))
                        self.ax.set_ylabel('Divisions')
                        self.ax.set_ylim(-5, 5)
                self.ax.legend()
            else:  # XY Plot
                ch1 = dataset.channels[0]
                ch2 = dataset.channels[1]
                if unit == 'Voltage':
                    ch1 = ch1.data
                    ch2 = ch2.data
                elif unit == 'Divisions':
                    ch1 = ch1.data_divisions
                    ch2 = ch2.data_divisions
                    self.ax.yaxis.set_major_locator(MultipleLocator(1))
                    self.ax.xaxis.set_major_locator(MultipleLocator(1))
                    self.ax.set_ylim(-5, 5)
                    self.ax.set_xlim(-5, 5)
                if mode == 'X: Ch1, Y: Ch2':
                    self.ax.plot(ch1, ch2)
                    self.ax.set_xlabel(f'{dataset.channels[0].name} ({unit})')
                    self.ax.set_ylabel(f'{dataset.channels[1].name} ({unit})')
                else:  # Ch2/Ch1
                    self.ax.plot(ch2, ch1)
                    self.ax.set_xlabel(f'{dataset.channels[1].name} ({unit})')
                    self.ax.set_ylabel(f'{dataset.channels[0].name} ({unit})')

        else:
            self.ax.text(0.5, 0.5, 'No Data', horizontalalignment='center', verticalalignment='center')
        self.ax.grid(True, linestyle='--', alpha=0.5)
        self.draw()


class MainWindow(QWidget):
    def __init__(self, disable_aliases=False):
        super().__init__()
        with importlib.resources.path("p1255", "gui.ui") as ui_file:
            uic.loadUi(ui_file, self)

        self.disable_aliases = disable_aliases

        self.plot_widget = PlotWidget()
        layout = QVBoxLayout(self.plot_placeholder)
        layout.addWidget(self.plot_widget)
        self.timer = None
        self.saving_directory = os.getcwd()

        self.p1255 = P1255()
        self.current_dataset = None

        if Path(ALIAS_FILE).is_file() and not self.disable_aliases:
            self.use_alias = True
            with open(ALIAS_FILE, "r") as f:
                self.aliases = yaml.safe_load(f)
        else:
            self.use_alias = False

        if self.use_alias:
            self.connection_stack.setCurrentIndex(1)
            self.alias_combo.addItems(self.aliases.keys())
            self.alias_combo.currentIndexChanged.connect(self.connect_to_ip)
        else:
            self.connection_stack.setCurrentIndex(0)

        self.connect_button.clicked.connect(self.connect_to_ip)
        self.help_button.setFixedWidth(30)
        self.help_button.clicked.connect(self.show_help)
        self.run_button.clicked.connect(self.toggle_run)
        self.capture_button.clicked.connect(self.capture_single)
        self.save_button.clicked.connect(self.save_data)
        self.unit_combo.currentIndexChanged.connect(self.update_current)
        self.display_mode_combo.currentIndexChanged.connect(self.update_current)

        if self.use_alias:
            self.connect_to_ip()
        self.capture_single()

    def show_help(self):
        QMessageBox.information(self, "Help", CONNECTION_HELP)

    def connect_to_ip(self):
        if self.use_alias:
            alias = self.alias_combo.currentText()
            ip, port = self.aliases[alias]
        else:
            ip = self.ip_input.text()
            port = self.port_input.text()
        print(f"Connecting to {ip}:{port}...")
        try:
            self.p1255.connect(ipaddress.IPv4Address(ip), int(port))
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to the oscilloscope: {e}")
            return
        self.connect_button.setText("Connected")

    def disconnect(self):
        self.p1255.disconnect()
        self.connect_button.setText("Connect")

    def toggle_run(self, checked):
        self.run_button.setChecked(checked)  # this is in case the button gets unchecked programmatically
        if checked:
            self.run_button.setText("Stop")
            self.start_updating()
        else:
            self.run_button.setText("Run Continuously")
            self.stop_updating()

    def update_current(self):
        self.plot_widget.update_plot(self.current_dataset, self.unit_combo.currentText(), self.display_mode_combo.currentText())

    def start_updating(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.capture_single)
        self.timer.start(500)  # milliseconds

    def stop_updating(self):
        if self.timer:
            self.timer.stop()
            self.timer = None

    def capture_single(self):
        try:
            self.current_dataset = self.p1255.capture()
            self.plot_widget.update_plot(self.current_dataset, self.unit_combo.currentText(), self.display_mode_combo.currentText())
        except ConnectionError:
            QMessageBox.critical(self, "Connection Error", "Connection lost.")
            self.toggle_run(False)
            self.disconnect()
        except Exception as e:
            QMessageBox.critical(self, "Capture Error", f"Failed to capture data: {e}")
            self.toggle_run(False)
            self.disconnect()

    def save_data(self):
        if not self.current_dataset:
            print("No data to save.")
            return

        filename = QFileDialog.getSaveFileName(
            self, "Save Data", self.saving_directory, "CSV Files (*.csv);;JSON Files (*.json);;Numpy Files (*.npz)"
        )[0]
        if not filename:
            return

        ext = Path(filename).suffix.lower()
        fmt = ext.lstrip('.')
        if fmt in ('csv', 'json', 'npz'):
            self.current_dataset.save(filename, fmt=fmt)
