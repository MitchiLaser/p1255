import socket
import struct
import ipaddress
import hexdump
from p1255 import command_mappings as cm
import numpy as np
from pathlib import Path
import pandas as pd
import yaml

VERBOSE = False


SCPI_RESPONSES = [
    "1K",
    "10K",
    "100K",
    "1M",
    "10M",
    "4",
    "16",
    "64",
    "128",
    "PEAK",
    "SAMPle",
    "AVERage",
]


class Data:
    def __init__(self, data: bytes):
        self.data = data
        
    def dump(self) -> None:
        hexdump.hexdump(self.data)
        
    def pop(self, length: int) -> bytes:
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
    class Channel:
        def __init__(self, data: Data, deep: bool = False):
            self.data = data
            self.deep = deep
            if self.deep:
                raise NotImplementedError("Deep waveform not implemented yet.")
            self.interpret_header()
            self.calculate_data()
            
        def interpret_header(self):
            self.name = self.data.pop(3).decode('ascii')
            self.unknown_1 = self.data.pop(24)
            self.total_time_s = cm.calc_timescale(self.data.pop(1)[0])
            self.unknown_2 = self.data.pop(3) # im guessing these 3
            self.offset_subdiv = struct.unpack("<i", self.data.pop(4))[0]
            self.voltscale_index = self.data.pop(1)[0]
            self.unknown_3 = self.data.pop(3)
            self.unknown_4 = self.data.pop(8).hex() #something with the trigger?
            self.frequency = struct.unpack("<f", self.data.pop(4))[0]
            self.unknown_5 = self.data.pop(8).hex()
            
            self.data_raw = np.array(struct.unpack("<" + "h" * (len(self.data) // 2), self.data.pop(len(self.data)))) # value in 1/25
            self.sample_time_ns = self.total_time_s / len(self.data_raw) * 1e9
        
        def calculate_data(self):
            self.data_screen = (self.data_raw + self.offset_subdiv) / 25 # find out this only works for STARTBIN not STARTMEMDEPTH
            self.data_volt = (self.data_raw / 25) * list(cm.VOLTBASE.keys())[self.voltscale_index]
            
    def __init__(self, data: Data, deep: bool = False):
        self.data = data
        self.deep = deep
        self.interpret_header()
        self.split_channels()
        self.add_important_info()
        
    def interpret_header(self):
        self.unknown_1 = self.data.pop(8)
        self.unknown_2 = self.data.pop(10)
        self.serial_number = self.data.pop(12).decode('ascii')
        self.unknown_3 = self.data.pop(19)
        self.n_channels = self.data.pop(1)[0].bit_count()
        self.unknown_4 = self.data.pop(12)
        
    def split_channels(self):
        if self.n_channels is None:
            raise ValueError("Header must be interpreted before splitting channels.")
        self.channels = []
        if len(self.data) % self.n_channels != 0:
            raise ValueError("Data length is not a multiple of the number of channels.")
        len_per_channel = len(self.data) // self.n_channels
        for i in range(self.n_channels):
            # assume all channels are the same length
            self.channels.append(Waveform.Channel(Data(self.data.pop(len_per_channel)), deep=self.deep))
            
    def add_important_info(self):
        self.data_screen = {ch.name: ch.data_screen for ch in self.channels}
        self.data_volt = {ch.name: ch.data_volt for ch in self.channels}
        self.time = np.linspace(start=(-1) * self.channels[0].total_time_s / 2, stop=self.channels[0].total_time_s / 2, num=len(self.channels[0].data_raw), endpoint=True)
        
        
    def save(self, path: Path, fmt='csv') -> None:
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
                'Channels': {
                    ch.name: {
                        '?1': ch.unknown_1.hex(),
                        'Total Time (s)': ch.total_time_s,
                        '?2': ch.unknown_2.hex(),
                        'Offset (subdiv)': ch.offset_subdiv,
                        'Voltscale Index': ch.voltscale_index,
                        '?3': ch.unknown_3.hex(),
                        '?4': ch.unknown_4,
                        'Frequency (Hz)': ch.frequency,
                        '?5': ch.unknown_5,
                        'Sample Time (ns)': ch.sample_time_ns,
                        'Data Screen (subdiv)': ch.data_screen.tolist(),
                        'Data Volt (V)': ch.data_volt.tolist(),
                    } for ch in self.channels
                }
            }
            with open(path.with_name(f"{path.stem}.yaml"), 'w') as f:
                yaml.dump(all, f)
        else:
            raise ValueError("Format must be 'csv' or 'yaml'.")

        



class P1255:
    def __init__(self):
        self.sock = None
        self.waiting_for_response = False
        
    def connect(self, ip: str, port: int = 3000, timeout = 5) -> None:
        """Establish a TCP connection to the oscilloscope.
        
        Parameters
        ----------
        ip : str
            The IP address of the oscilloscope.
        port : int, optional
            The port number to connect to (default is 3000).
        timeout : int, optional
            The timeout for the connection in seconds (default is 5).
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        try:
            self.sock.connect((ip, port))
        except (OSError, socket.timeout, ConnectionRefusedError) as e:
            self.sock.close()
            self.sock = None
            raise e
        
    def disconnect(self) -> None:
        """Close the TCP connection to the oscilloscope."""
        if self.sock:
            self.sock.close()
            self.waiting_for_response = False
            self.sock = None
            
    def send_command(self, command: str) -> None:
        """Send a command to the oscilloscope.
        
        Parameters
        ----------
        command : str
            The command to send (as a hex string).
        """
        if self.waiting_for_response:
            raise RuntimeError("Cannot send command while waiting for response.")
        if not self.sock:
            hexdump.hexdump(bytes.fromhex(command))
            print("Not connected, command not sent.")
            return
        try:
            self.sock.sendall(bytes.fromhex(command))
        except OSError as e:
            self.disconnect()
            raise e
        
    def send_scpi_command(self, command: str) -> None:
        """Send an SCPI command to the oscilloscope.
        
        Parameters
        ----------
        command : str
            The SCPI command to send.
        """
        self.send_command(command.encode('ascii').hex())
        
    def send_modify_command(self, command: str) -> None:
        length = len(command) // 2
        length_str = struct.pack("<I", length).hex()
        full_command = hexstr("M:") + length_str + command
        self.send_command(full_command)
        
    def receive_scpi_response(self) -> str:
        """Receive an SCPI response from the oscilloscope.

        Returns
        -------
        response : str
            The received SCPI response.
        """
        if not self.sock:
            raise ConnectionError("Not connected to the oscilloscope.")
        self.waiting_for_response = True
        response = ""
        try:
            while True:
                response += self.sock.recv(1).decode('ascii')
                if response in SCPI_RESPONSES:
                    break
        except TimeoutError:
            print(response)
            raise TimeoutError("Timeout while waiting for SCPI response.")
        except OSError as e:
            self.disconnect()
            raise e
        self.waiting_for_response = False
        return response

    def receive_data(self) -> Data:
        """Receive data from the oscilloscope.
        
        Returns
        -------
        data
            The received data.
        """
        if not self.sock:
            raise ConnectionError("Not connected to the oscilloscope.")
        self.waiting_for_response = True
        received = 0
        length_buffer = bytearray(4)
        try:
            while received < 4:
                received += self.sock.recv_into(memoryview(length_buffer)[received:])
        except OSError as e:
            self.disconnect()
            raise e
        length = struct.unpack("<I", length_buffer)[0] + 8 # Wtf are these 8
        if VERBOSE:
            print(f"Expecting {length} bytes of data.")
        
        received = 0
        data_buffer = bytearray(length)
        try:
            while received < length:
                received += self.sock.recv_into(memoryview(data_buffer)[received:])
                if VERBOSE:
                    print(f"Received {received}/{length} bytes of data.")
        except OSError as e:
            self.disconnect()
            raise e
        data = Data(bytes(data_buffer))
        self.waiting_for_response = False
        return data

    
    def interpret_bmp(self, data: Data, output: Path) -> dict:
        """Interpret BMP image data received from the oscilloscope.
        
        Parameters
        ----------
        data : Data
            The raw BMP data received from the oscilloscope.
        output : Path
            The path to save the BMP file.
        """
        unknown = data.pop(8)
        rest = data.pop(len(data))
        with open(output, 'wb') as f:
            f.write(rest)

    def get_waveform(self) -> Waveform:
        """Get the waveform data from the oscilloscope.
        
        Returns
        -------
        Waveform
            The interpreted waveform data.
        """
        self.send_scpi_command(cm.GET_WAVEFORM)
        data = self.receive_data()
        wf = Waveform(data)
        return wf
        
    
    def get_deep_waveform(self) -> Waveform:
        """Get the deep waveform data from the oscilloscope.
        
        Returns
        -------
        Waveform
            The interpreted deep waveform data.
        """
        self.send_scpi_command(cm.GET_DEEP_WAVEFORM)
        data = self.receive_data()
        wf = Waveform(data, deep=True)
        return wf
    
    
    def get_bmp(self, output: Path) -> None:
        """Get a BMP screenshot from the oscilloscope and save it to a file.
        
        Parameters
        ----------
        output : Path
            The path to save the BMP file.
        """
        self.send_scpi_command(cm.GET_BMP)
        data = self.receive_data()
        self.interpret_bmp(data, output)
        
    def set_ip_configuration(
        self, 
        ip = "192.168.1.72", 
        port = 3000, 
        subnet = "255.255.255.0", 
        gateway = "192.168.1.1"
        ):
        """Set the IP configuration of the oscilloscope.
        
        Parameters
        ----------
        ip : str
            The IP address to set.
        port : int
            The port number to set.
        subnet : str
            The subnet mask to set.
        gateway : str
            The gateway address to set.
        """
        cmd = cm.network(ip, port, gateway, subnet)
        self.send_modify_command(cmd)
        
    def set_trigger_configuration(
        self,
        coupling = "DC",
        mode = "AUTO",
        slope = "RISING",
        level = 0,
        channel = 1,
        type = "SINGLE",
        ):
        """Set the trigger configuration of the oscilloscope.
        
        Parameters
        ----------
        coupling : str
            The coupling mode. One of 'AC', 'DC', 'LF', 'HF'
        mode : str
            The trigger mode. One of 'AUTO', 'NORM', 'SINGLE'
        slope : str
            The trigger slope. One of 'RISING', 'FALLING'
        level : int
            The trigger level in Volts. Range is +5V to -7V in steps of 40mV. (Will be rounded to nearest step)
        channel : int
            The channel to trigger on. 1 or 2
        type : str
            The trigger type. 'SINGLE' or 'ALTERNATE'
        """
        if coupling not in cm.TRIGGER_COUPLING:
            raise ValueError(f"Invalid coupling mode. Must be one of {list(cm.TRIGGER_COUPLING.keys())}.")
        if mode not in cm.TRIGGER_MODE:
            raise ValueError(f"Invalid trigger mode. Must be one of {list(cm.TRIGGER_MODE.keys())}.")
        if slope not in cm.TRIGGER_SLOPE:
            raise ValueError(f"Invalid trigger slope. Must be one of {list(cm.TRIGGER_SLOPE.keys())}.")
        if channel not in cm.CHANNEL:
            raise ValueError(f"Invalid channel. Must be one of {list(cm.CHANNEL.keys())}.")
        if type not in cm.TRIGGER_TYPE:
            raise ValueError(f"Invalid trigger type. Must be one of {list(cm.TRIGGER_TYPE.keys())}.")
        if not (-7.0 <= level <= 5.0):
            raise ValueError("Invalid trigger level. Must be between -7V and +5V.")
        
        repeating = (
            hexstr("MTR")
            + cm.TRIGGER_TYPE[type]
            + cm.CHANNEL[channel]
            )
        cmd = (
            repeating
            + "02"
            + cm.TRIGGER_COUPLING[coupling]
            + repeating
            + "03"
            + cm.TRIGGER_MODE[mode]
            + repeating
            + "04"
            + "00000000"
            + repeating
            + "05"
            + cm.TRIGGER_SLOPE[slope]
            + repeating
            + "06"
            + cm.trigger_voltage(level)
        )
        self.send_modify_command(cmd)
        
        
    def set_channel_configuration(
        self,
        channel: int,
        probe_rate: int = 1,
        coupling: str = "DC",
        voltbase_V: float = 1.0,
    ):
        """Set the channel configuration of the oscilloscope.
        
        Parameters
        ----------
        channel : int
            The channel to configure. 1 or 2
        probe_rate : int
            The probe rate. One of 1, 10, 100, 1000
        coupling : str
            The coupling mode. One of 'DC', 'AC', 'GND'
        voltbase_V : float
            The voltbase in Volts. One of 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10
        """
        if channel not in cm.CHANNEL:
            raise ValueError(f"Invalid channel. Must be one of {list(cm.CHANNEL.keys())}.")
        if probe_rate not in cm.PROBERATE:
            raise ValueError(f"Invalid probe rate. Must be one of {list(cm.PROBERATE.keys())}.")
        if coupling not in cm.CHANNEL_COUPLING:
            raise ValueError(f"Invalid coupling mode. Must be one of {list(cm.CHANNEL_COUPLING.keys())}.")
        if voltbase_V not in cm.VOLTBASE:
            raise ValueError(f"Invalid voltbase. Must be one of {list(cm.VOLTBASE.keys())}.")
        
        cmd = (
            hexstr("MCH")
            + cm.CHANNEL[channel]
            + hexstr("p")
            + cm.PROBERATE[probe_rate]
            + hexstr("c")
            + cm.CHANNEL_COUPLING[coupling]
            + hexstr("v")
            + cm.VOLTBASE[voltbase_V]
        )
        self.send_modify_command(cmd)
        
    

def hexstr(ascii):
    return ascii.encode("ASCII").hex()

def ascii(hexstr):
    return bytes.fromhex(hexstr).decode("ASCII")
