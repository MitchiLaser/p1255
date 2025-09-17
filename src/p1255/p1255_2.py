import socket
import struct
import ipaddress
import hexdump
import command_mappings as cm
import numpy as np
from pathlib import Path

VERBOSE = True


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
        chunk = self.data[:length]
        self.data = self.data[length:]
        return chunk
    
    def __len__(self) -> int:
        return len(self.data)
    
        


class P1255:
    def __init__(self):
        self.sock = None
        
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
            self.sock = None
            
    def send_command(self, command: str) -> None:
        """Send a command to the oscilloscope.
        
        Parameters
        ----------
        command : str
            The command to send (as a hex string).
        """
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

    def receive_scpi_response(self) -> str:
        """Receive an SCPI response from the oscilloscope.

        Returns
        -------
        response : str
            The received SCPI response.
        """
        if not self.sock:
            raise ConnectionError("Not connected to the oscilloscope.")
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
        received = 0
        length_buffer = bytearray(4)
        try:
            while received < 4:
                received += self.sock.recv_into(memoryview(length_buffer)[received:])
        except OSError as e:
            self.disconnect()
            raise e
        length = struct.unpack("<I", length_buffer)[0]
        print(f"Expecting {length} bytes of data.")
        
        received = 0
        data_buffer = bytearray(length)
        try:
            while received < length:
                received += self.sock.recv_into(memoryview(data_buffer)[received:])
                print(f"Received {received}/{length} bytes of data.")
        except OSError as e:
            self.disconnect()
            raise e
        data = Data(bytes(data_buffer))
        return data


    def interpret_waveform(self, data: Data) -> dict:
        """Interpret the waveform data received from the oscilloscope.
        
        Parameters
        ----------
        data : Data
            The raw data received from the oscilloscope.
        
        """
        # the first 8 bytes i dont know what they are
        # then 10 more bytes i dont know what they are
        # then 12 bytes of serial number
        # then 19 bytes i dont know what they are
        # then 1 byte where each bit represents an active channel
        # then 12 bytes of unknown data
        
        
        """
        
        Somewhere is the trigger status, frequency, Period
        
        SP is the sampling Period 
        
        
        """
        
        
        head = {
            '?1': data.pop(8),
            '?2': data.pop(10),
            'SN': data.pop(12).decode('ascii'),
            '?3': data.pop(19),
            'n_channels': data.pop(1)[0].bit_count(),
            '?4': data.pop(12),
        }
        
        # split the rest of the data into channels
        len_remaining = len(data)
        n_channels = head['n_channels']
        if len_remaining % n_channels != 0:
            raise ValueError("Data length is not a multiple of the number of channels.")
        len_per_channel = len_remaining // n_channels
        
        channels = [Data(data.pop(len_per_channel)) for _ in range(n_channels)]
        
        return head, channels
    
    def interpret_channel(self, data: Data) -> dict:
        """Interpret a single channel of waveform data.
        
        Parameters
        ----------
        data : Data
            The raw data for a single channel.
            
        Returns
        -------
        dict
            A dictionary containing the interpreted channel data.
        """
        
        out = {
            'name': data.pop(3).decode('ascii'),
            '?1': data.pop(24),
            'timescale': data.pop(1)[0],
            '?2': data.pop(3), # im guessing these 3 bytes could be included in the timescale (they appear to be 0)
            'offset_subdiv': struct.unpack("<i", data.pop(4))[0],
            'voltscale_index': data.pop(1)[0],
            '?3': data.pop(3),
            '?4': data.pop(8).hex(),
            'frequency': struct.unpack("<f", data.pop(4))[0],
            '?5': data.pop(8).hex(),
            'raw_data': np.array(struct.unpack("<" + "h" * (len(data) // 2), data.pop(len(data)))) # value in 1/25 of a division (not offset yet)
        }
        
        print('factor: ', list(cm.VOLTBASE.keys())[out['voltscale_index']] / 25)
        
        # out['data_screen'] = (out['raw_data'] + out['offset_subdiv']) / 25 # find out this only works for STARTBIN not STARTMEMDEPTH
        out['data_volt'] = (out['raw_data'] / 25) * list(cm.VOLTBASE.keys())[out['voltscale_index']]
        return out
    
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

    def get_waveform(self) -> dict:
        """Get the waveform data from the oscilloscope.
        
        Returns
        -------
        dict
            A dictionary containing the interpreted waveform data.
        """
        self.send_scpi_command(cm.GET_WAVEFORM)
        data = self.receive_data()
        wf_dict, channels = self.interpret_waveform(data)
        for ch in channels:
            ch_dict = self.interpret_channel(ch)
            wf_dict[ch_dict['name']] = ch_dict
        return wf_dict
    
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
