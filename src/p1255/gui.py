from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
)
from PyQt5 import uic
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator
import matplotlib.pyplot as plt
import os
from p1255.p1255 import P1255, Waveform
from p1255.constants import CONNECTION_HELP, COLORS
import ipaddress
from pathlib import Path
import yaml
import importlib.resources


plt.style.use('dark_background')

ALIAS_FILE = Path().home() / ".p1255_ip_aliases.yaml"


class PlotWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure()
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)

    def update_plot(self, wf: Waveform, unit, mode):
        """Update the plot with data and unit

        Parameters
        ----------
        wf : Waveform
            The waveform data to plot.
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
        
        # get the data in the desired unit
        data = []
        if unit == 'Divisions':
            for channel in wf.channels:
                self.ax.set_xlabel('Divisions')
                self.ax.set_ylabel('Divisions')
                data.append(channel.data_screen)
        else:  # Voltage
            self.ax.set_xlabel('Voltage (V)')
            self.ax.set_ylabel('Voltage (V)')
            for channel in wf.channels:
                data.append(channel.data_volt)
                
        if not data:
            self.ax.text(0.5, 0.5, 'No channels in dataset',
                        ha='center', va='center', transform=self.ax.transAxes)
            self.ax.grid(True, linestyle='--', alpha=0.5)
            self.draw()
            return
        
        if mode == 'Normal':
            self.ax.set_xlabel('Time (s)')
            for i, channel in enumerate(wf.channels):
                self.ax.plot(wf.time, data[i], label=channel.name, color=COLORS[channel.name])
            self.ax.legend()
        else: # XY Plot
            if len(wf.channels) < 2:
                self.ax.text(0.5, 0.5, 'XY-Mode needs CH1 & CH2',
                            ha='center', va='center', transform=self.ax.transAxes)
                self.ax.grid(True, linestyle='--', alpha=0.5)
                self.draw()
                return
            if mode == 'X: Ch1, Y: Ch2':
                x = data[0]
                y = data[1]
            else:  # Ch2/Ch1
                x = data[1]
                y = data[0]
            self.ax.plot(x, y)
            
        self.ax.grid(True, linestyle='--', alpha=0.5)
        

        self.ax.relim()
        self.ax.autoscale_view()
        if unit == 'Divisions':
            self.ax.yaxis.set_major_locator(MultipleLocator(1))
            self.ax.set_ylim(-5, 5)
            if mode != 'Normal':
                self.ax.xaxis.set_major_locator(MultipleLocator(1))
                self.ax.set_xlim(-5, 5)
        
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
        self.wf_dict = None
        self.channels = []

        if Path(ALIAS_FILE).is_file() and not self.disable_aliases:
            self.use_alias = True
            with open(ALIAS_FILE, "r") as f:
                self.aliases = yaml.safe_load(f)
        else:
            self.use_alias = False

        if self.use_alias:
            self.connection_stack.setCurrentIndex(1)
            self.alias_combo.addItems(self.aliases.keys())
            self.alias_combo.currentIndexChanged.connect(self.disconnect) # stellt sicher, dass bei Alias Wechsel der Connect Button sich wieder in Default stellt.
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
        self._xy_popup_active = False #checkt ob schon ein Pop Up da ist

        #self.capture_single() # so we can see no data but a grid, looks better xD, you can delete this line if you want to

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
            self.p1255.connect(str(ipaddress.IPv4Address(ip)), int(port))
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to the oscilloscope: {e}")
            self.connect_button.setText("Connect")
            self.connect_button.setStyleSheet("color: black;")
            return
        self.connect_button.setText("Connected")
        self.connect_button.setStyleSheet("color: green;")
        print(f"Connected to {ip}:{port}")

    def disconnect(self):
        self.p1255.disconnect()
        self.connect_button.setText("Connect")
        self.connect_button.setStyleSheet("color: black;")

    def toggle_run(self, checked):
        self.run_button.setChecked(checked)  # this is in case the button gets unchecked programmatically
        if checked:
            self.run_button.setText("Stop")
            self.start_updating()
        else:
            self.run_button.setText("Run Continuously")
            self.stop_updating()

    def update_current(self):
        self.plot_widget.update_plot(self.current_wf, self.unit_combo.currentText(), self.display_mode_combo.currentText())

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
            if not self.p1255.waiting_for_response:
                self.current_wf = self.p1255.get_waveform()
                self.update_current()
        except ConnectionError:
            QMessageBox.critical(self, "Connection Error", "Connection lost.")
            self.toggle_run(False)
            self.disconnect()
        except Exception as e:
            QMessageBox.critical(self, "Capture Error", f"Failed to capture data: {e}")
            self.toggle_run(False)
            self.disconnect()

    def save_data(self):
        if not self.current_wf:
            print("No data to save.")
            return

        filename = QFileDialog.getSaveFileName(
            self, "Save Data", self.saving_directory, "CSV Files (*.csv);;YAML Files (*.yaml)"
        )[0]
        if not filename:
            return

        ext = Path(filename).suffix.lower()
        fmt = ext.lstrip('.')
        if fmt in ('csv', 'yaml'):
            self.current_wf.save(Path(filename), fmt=fmt)
        else:
            QMessageBox.critical(self, "Save Error", f"Unsupported file format: {ext}")
            return
