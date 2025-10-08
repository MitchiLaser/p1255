from .constants import COLORS
from . import commands as cm
from matplotlib.ticker import MultipleLocator
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from pathlib import Path
from PIL import Image
from io import BytesIO
import hexdump
import struct
import math


class Data:
    """A simple class to handle binary data."""

    def __init__(self, data: bytes):
        self.data = data

    def dump(self) -> None:
        """Dump the data in a human-readable format."""
        hexdump.hexdump(self.data)

    def pop(self, length: int) -> bytes:
        """Pop `length` bytes from the start of the data."""
        if len(self.data) < length:
            raise ValueError("Not enough data to pop.")
        chunk = self.data[:length]
        self.data = self.data[length:]
        return chunk

    def __len__(self) -> int:
        return len(self.data)

    def copy(self) -> "Data":
        return Data(self.data)


class Waveform:
    """Waveform data structure."""

    class Channel:
        """Channel data structure."""

        def __init__(self, data: Data, memdepth: str = None):
            self.data = data
            self.memdepth = memdepth
            self.read_in_data()
            self.calculate_data()

        def read_in_data(self):
            self.name = self.data.pop(3).decode('ascii')
            self.unknown_1: bytes = self.data.pop(8)
            self.unknown_2: int = struct.unpack('<i', self.data.pop(4))[0]
            self.unknown_3: int = struct.unpack('<i', self.data.pop(4))[0]
            self.unknown_4: int = struct.unpack('<i', self.data.pop(4))[0]
            self.unknown_5: int = struct.unpack('<i', self.data.pop(4))[0]
            self.timescale_index: int = struct.unpack("<i", self.data.pop(4))[0]
            self.offset_subdiv: int = struct.unpack("<i", self.data.pop(4))[0]
            self.voltscale_index: int = struct.unpack("<i", self.data.pop(4))[0]
            self.unknown_8: bytes = self.data.pop(8)
            self.frequency: float = struct.unpack("<f", self.data.pop(4))[0]
            self.maybe_period_us: float = struct.unpack('<f', self.data.pop(4))[0]
            self.unknown_10: float = struct.unpack('<f', self.data.pop(4))[0]
            self.data_raw: np.ndarray = np.array(struct.unpack("<" + "h" * (len(self.data) // 2), self.data.pop(len(self.data))))

            assert len(self.data) == 0, "Did not consume all data for channel!"

        def calculate_data(self):
            """Calculate the screen and voltage data from the raw data."""
            self.sample_time_ns = self.total_time_s / len(self.data_raw) * 1e9
            self.voltscale = list(cm.VOLTBASE.keys())[self.voltscale_index]  # in Volts/Div
            self.total_time_s = self.calc_timescale(self.timescale_index)
            
            if self.memdepth is not None:
                self.data_screen = self.deep_to_screen(self.data_raw, self.voltscale, self.offset_subdiv)
                self.data_volt = self.deep_to_volt(self.data_raw, self.voltscale, self.offset_subdiv)
            else:
                self.data_screen = self.normal_to_screen(self.data_raw, self.voltscale, self.offset_subdiv)
                self.data_volt = self.normal_to_volt(self.data_raw, self.voltscale, self.offset_subdiv)

        @staticmethod
        def normal_to_screen(ch: np.ndarray, scale: float, off: int) -> np.ndarray:
            return (ch + off) / 25

        @staticmethod
        def normal_to_volt(ch: np.ndarray, scale: float, off: int) -> np.ndarray:
            return ch * scale / 25  # I would say this is correct, actually probably use 5/2**8 here instead of 1/25

        @staticmethod
        def deep_to_volt(ch: np.ndarray, scale: float, off: int) -> np.ndarray:
            return scale * (ch / 2**8 - off) / 25

        @staticmethod
        def deep_to_screen(ch: np.ndarray, scale: float, off: int) -> np.ndarray:
            return (ch / 2**8) / 25

        @staticmethod
        def calc_timescale(number: int) -> float:
            exp = math.floor(number / 3)
            mant = {0: 1, 1: 2, 2: 5}[number % 3]
            time_per_div = mant * (10**exp)
            return 15 * time_per_div * 1e-9  # times 15 divisions on the screen, convert from nanoseconds to seconds

    def __init__(self, data: Data, memdepth: str = None):
        self.data = data
        self.memdepth = memdepth
        self.read_in_data()
        self.split_channels()
        self.add_important_info()

    def read_in_data(self):
        self.unknown_1: bytes = self.data.pop(8)
        self.unknown_2: int = self.data.pop(10)
        self.serial_number: str = self.data.pop(12).decode('ascii')
        self.unknown_3: bytes = self.data.pop(19)
        self.n_channels: int = self.data.pop(1)[0].bit_count()
        self.trig_pos_us: float = struct.unpack('<f', self.data.pop(4))[0]
        self.unknown_4: bytes = self.data.pop(8) # somewhat changes with the vertical offset of the trigger channel

    def split_channels(self):
        """Split the remaining data into channels."""
        self.channels = []
        if len(self.data) % self.n_channels != 0:
            raise ValueError("Data length is not a multiple of the number of channels.")
        len_per_channel = len(self.data) // self.n_channels
        for i in range(self.n_channels):
            # assume all channels are the same length
            self.channels.append(Waveform.Channel(Data(self.data.pop(len_per_channel)), memdepth=self.memdepth))
            
        assert len(self.data) == 0, "Did not consume all data for waveform!"

    def add_important_info(self):
        """Add important info from the Channels."""
        self.data_screen = {ch.name: ch.data_screen for ch in self.channels}
        self.data_volt = {ch.name: ch.data_volt for ch in self.channels}
        self.time = np.linspace(
            start=(-1) * self.channels[0].total_time_s / 2,
            stop=self.channels[0].total_time_s / 2,
            num=len(self.channels[0].data_raw),
            endpoint=True,
        )

    def save(self, path: Path, fmt='csv') -> None:
        """Save the waveform data to a file.

        Parameters
        ----------
        path : Path
            The path to save the file to (without extension).
        fmt : str
            The format to save the file in. One of 'csv' or 'yaml'.
        """
        if fmt == 'csv':
            df = pd.DataFrame({'Time': self.time, **self.data_volt})
            df.to_csv(path.with_name(f"{path.stem}.csv"), index=False)
        elif fmt == 'yaml':
            all = {
                '?1': self.unknown_1.hex(),
                '?2': self.unknown_2.hex(),
                'Serial Number': self.serial_number,
                '?3': self.unknown_3.hex(),
                '?4': self.unknown_4.hex(),
                'trig_pos_us': self.trig_pos_us,
                'memdepth': self.memdepth,
                'Channels': {
                    ch.name: {
                        '?1': ch.unknown_1.hex(),
                        '?2': ch.unknown_2,
                        '?3': ch.unknown_3,
                        '?4': ch.unknown_4,
                        '?5': ch.unknown_5,
                        'Total Time (s)': ch.total_time_s,
                        '?6': ch.unknown_6.hex(),
                        'Offset (subdiv)': ch.offset_subdiv,
                        'Voltscale Index': ch.voltscale_index,
                        '?7': ch.unknown_7.hex(),
                        '?8': ch.unknown_8.hex(),
                        'Frequency (Hz)': ch.frequency,
                        '?9': ch.unknown_9,
                        '?10': ch.unknown_10,
                        'Sample Time (ns)': ch.sample_time_ns,
                        'Data Screen (subdiv)': ch.data_screen.tolist(),
                        'Data Volt (V)': ch.data_volt.tolist(),
                    }
                    for ch in self.channels
                },
            }
            with open(path.with_name(f"{path.stem}.yaml"), 'w') as f:
                yaml.dump(all, f)
        else:
            raise ValueError("Format must be 'csv' or 'yaml'.")

    def debug(self) -> None:
        """Print all available info gathered from the waveform."""

        def small_hexdump(data: bytes) -> None:
            print(data.hex(sep=" ", bytes_per_sep=1))
            print(data.decode('ascii', errors='replace'))

        print("Waveform Info")
        print("-------------")
        print("Unknown 1:")
        small_hexdump(self.unknown_1)
        print("Unknown 2:")
        small_hexdump(self.unknown_2)
        print(f"Serial Number: {self.serial_number}")
        print("Unknown 3:")
        small_hexdump(self.unknown_3)
        print(f"Number of Channels: {self.n_channels}")
        print(f"Trigger Position: {self.trig_pos_us} us")
        print("Unknown 4:")
        small_hexdump(self.unknown_4)
        print(f"Memory Depth: {self.memdepth}")
        print()
        for i, ch in enumerate(self.channels):
            print(f"Channel {i + 1} Info")
            print("----------------")
            print(f"Name: {ch.name}")
            print("Unknown 1:")
            small_hexdump(ch.unknown_1)
            print(f"Unknown 2: {ch.unknown_2}")
            print(f"Unknown 3: {ch.unknown_3}")
            print(f"Unknown 4: {ch.unknown_4}")
            print(f"Unknown 5: {ch.unknown_5}")
            print(f"Total Time: {ch.total_time_s} s")
            print("Unknown 6:")
            small_hexdump(ch.unknown_6)
            print(f"Offset: {ch.offset_subdiv} subdivisions")
            print(f"Voltscale Index: {ch.voltscale_index} ({ch.voltscale} V/Div)")
            print("Unknown 7:")
            small_hexdump(ch.unknown_7)
            print("Unknown 8:")
            small_hexdump(ch.unknown_8)
            print(f"Frequency: {ch.frequency} Hz")
            print(f"Unknown 9: {ch.unknown_9}")
            print(f"Unknown 10: {ch.unknown_10}")
            print(f"Data Points: {len(ch.data_raw)}")
            print()

    def plot(self) -> None:
        """Plot the waveform data."""
        with plt.style.context('dark_background'):
            fig, ax = plt.subplots()
            x = np.linspace(-7.6, 7.6, len(self.time))
            for ch in self.channels:
                ax.plot(
                    x,
                    ch.data_screen,
                    label=f"{ch.name:<3} | {ch.voltscale:4.2f}V/Div | Offset: {ch.offset_subdiv:3} Div | Freq: {ch.frequency:6.2f}Hz",
                    color=COLORS[ch.name],
                )

            ax.set_ylim(-5, 5)
            ax.set_xlim(-7.6, 7.6)
            ax.xaxis.set_major_locator(MultipleLocator(1))
            ax.yaxis.set_major_locator(MultipleLocator(1))
            ax.set_aspect('equal', adjustable='box')
            ax.tick_params(
                bottom=False,
                left=False,
                labelbottom=False,
                labelleft=False,
            )
            ax.legend(loc='upper left', bbox_to_anchor=(0, -0.01), frameon=True)
            for text in ax.legend_.get_texts():
                text.set_fontfamily('monospace')

            ax.set_title(
                f"""Waveform from {self.serial_number}
Total Time: {self.channels[0].total_time_s * 1e3:.2f} ms
Samples: {len(self.time)}""",
                pad=20,
                loc='left',
            )
            ax.grid(which='both', linestyle=':', linewidth=0.5, alpha=0.5)
            ax.axhline(0, color='white', linewidth=0.5, linestyle=':')
            ax.axvline(0, color='white', linewidth=0.5, linestyle=':')

            plt.tight_layout()
            plt.show()


class BMP:
    def __init__(self, data: Data):
        self.data = data
        self.interpret_header()

    def interpret_header(self):
        self.unknown: bytes = self.data.pop(8)
        self.bmp_data: bytes = self.data.pop(len(self.data))

    def save(self, path: Path) -> None:
        """Save the BMP data to a file.

        Parameters
        ----------
        path : Path
            The path to save the BMP file to.
        """
        with open(path, 'wb') as f:
            f.write(self.bmp_data)

    def plot(self) -> None:
        """Plot the BMP data."""
        with BytesIO(self.bmp_data) as bio:
            img = Image.open(bio)
            img.show()
