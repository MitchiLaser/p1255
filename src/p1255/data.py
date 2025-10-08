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
            self.timebase_index: int = struct.unpack("<i", self.data.pop(4))[0]
            self.offset_subdiv: int = struct.unpack("<i", self.data.pop(4))[0]
            self.voltscale_index: int = struct.unpack("<i", self.data.pop(4))[0]
            self.unknown_6: bytes = self.data.pop(8)
            self.frequency: float = struct.unpack("<f", self.data.pop(4))[0]
            self.maybe_period_us: float = struct.unpack('<f', self.data.pop(4))[0]
            self.unknown_7: float = struct.unpack('<f', self.data.pop(4))[0]
            self.data_raw: np.ndarray = np.array(struct.unpack("<" + "h" * (len(self.data) // 2), self.data.pop(len(self.data))))

            assert len(self.data) == 0, "Did not consume all data for channel!"

        def calculate_data(self):
            """Calculate the screen and voltage data from the raw data."""
            self.timebase_us_per_div = cm.TIMEBASELIST[self.timebase_index]  # in microseconds per division
            self.total_time_s = self.timebase_us_per_div * 15 * 1e-6  # total time in seconds (15 divisions on the screen)
            self.voltscale = cm.VOLTBASELIST[self.voltscale_index]  # in Volts/Div
            
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
            raise NotImplementedError("YAML saving is not implemented yet.")
        else:
            raise ValueError("Format must be 'csv' or 'yaml'.")

    def plot(self) -> None:
        """Plot the waveform data."""
        with plt.style.context('dark_background'):
            fig, ax = plt.subplots()
            x = np.linspace(-7.6, 7.6, len(self.time))
            for ch in self.channels:
                ax.plot(
                    x,
                    ch.data_screen,
                    label=f"{ch.name:<3} | {ch.voltscale:4.2f}V/Div | Offset: {ch.offset_subdiv:3} Div | Freq: {ch.frequency:6.2f}Hz | Period: {ch.maybe_period_us:6.2f}us | {ch.timebase_us_per_div:6.2f}us/Div",
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
Trigger Position: {self.trig_pos_us} us
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
