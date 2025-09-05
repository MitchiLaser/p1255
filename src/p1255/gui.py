from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QComboBox,
    QFileDialog,
)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator
import os
from p1255.p1255 import P1255
from p1255.constants import CONNECTION_HELP
import ipaddress
from PyQt5.QtWidgets import QMessageBox
from pathlib import Path
import yaml


ALIAS_FILE = Path().home() / ".p1255_ip_aliases.yaml"


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
                    self.ax.set_ylabel('Divisions')
                    self.ax.set_ylim(-5,5)
            self.ax.legend()
        else:
            self.ax.text(0.5, 0.5, 'No Data', horizontalalignment='center', verticalalignment='center')
        self.ax.grid(True)
        self.draw()


class MainWindow(QWidget):
    def __init__(self, disable_aliases=False):
        super().__init__()
        self.disable_aliases = disable_aliases

        self.setWindowTitle("P1255 Oscilloscope GUI")
        self.plot_widget = PlotWidget()
        self.timer = None
        self.saving_directory = os.getcwd()

        self.init_ui()

        self.p1255 = P1255()
        self.current_dataset = None
        
        self.capture_single()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.voltage_mode = True

        # Plot
        layout.addWidget(self.plot_widget)

        # Controls
        controls = QVBoxLayout()
        
        connection_controls = QHBoxLayout()
        data_controls = QHBoxLayout()
        controls.addLayout(connection_controls)
        controls.addLayout(data_controls)
        
        if ALIAS_FILE.exists() and not self.disable_aliases:
            # Branch 1 - Alias File
            self.use_alias = True
            with open(ALIAS_FILE, "r") as f:
                self.aliases = yaml.safe_load(f)
            if self.aliases:
                self.alias_combo = QComboBox()
                self.alias_combo.addItems(self.aliases.keys())
                connection_controls.addWidget(QLabel("Device:"))
                connection_controls.addWidget(self.alias_combo)

        else:
            # Branch 2 Custom IP Input
            self.use_alias = False
            self.ip_input = QLineEdit()
            self.ip_input.setPlaceholderText("Enter IP Address")
            connection_controls.addWidget(QLabel("IP Address:"))
            connection_controls.addWidget(self.ip_input)
            self.port_input = QLineEdit()
            self.port_input.setText("3000")
            connection_controls.addWidget(QLabel("Port:"))
            connection_controls.addWidget(self.port_input)
        

        # Connect Button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_to_ip)
        connection_controls.addWidget(self.connect_button)

        # Help Button (Question Mark)
        self.help_button = QPushButton("?")
        self.help_button.setFixedWidth(30)
        self.help_button.clicked.connect(self.show_help)
        connection_controls.addWidget(self.help_button)

        # Run and Capture Buttons
        self.run_button = QPushButton("Run Continuously")
        self.run_button.setCheckable(True)
        self.run_button.clicked.connect(self.toggle_run)
        data_controls.addWidget(self.run_button)

        self.capture_button = QPushButton("Capture Single")
        self.capture_button.clicked.connect(self.capture_single)
        data_controls.addWidget(self.capture_button)

        self.save_button = QPushButton("Save Data")
        self.save_button.clicked.connect(self.save_data)
        data_controls.addWidget(self.save_button)
        
        self.mode_button = QPushButton("Toggle Voltage/Divisions")
        self.mode_button.setCheckable(True)
        self.mode_button.clicked.connect(self.toggle_voltage_mode)
        data_controls.addWidget(self.mode_button)

        

        layout.addLayout(controls)

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
        self.run_button.setChecked(checked) # this is in case the button gets unchecked programmatically
        if checked:
            self.run_button.setText("Stop")
            self.start_updating()
        else:
            self.run_button.setText("Run Continuously")
            self.stop_updating()
            
    def toggle_voltage_mode(self):
        self.voltage_mode = not self.voltage_mode
        self.plot_widget.update_plot(self.current_dataset, self.voltage_mode)

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
            self.plot_widget.update_plot(self.current_dataset, self.voltage_mode)
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
