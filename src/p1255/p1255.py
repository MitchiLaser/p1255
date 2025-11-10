from . import commands as cm
from .data import Waveform, Data, BMP
import socket
import struct
import hexdump
from tqdm import tqdm


class P1255:
    def __init__(self, ip: str = None, port: int = 3000, timeout: int = 5):
        self.sock = None
        self.waiting_for_response = False
        if ip is not None:
            self.connect(ip, port, timeout)

    def connect(self, ip: str, port: int = 3000, timeout=5) -> None:
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
        """Send a modify command to the oscilloscope.

        For that purpose the command is prefixed with ":M", followed by the length of the command in bytes (as a little-endian 4-byte integer).
        """
        length = len(command) // 2
        length_str = struct.pack(">I", length).hex()
        full_command = hexstr(":M") + length_str + command
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
        response_hex_str = ""

        try:
            while True:
                b = self.sock.recv(1)
                response += b.decode('ascii')
                response_hex_str += b.hex()
                if response in cm.SCPI_RESPONSES:
                    break
        except TimeoutError:
            print(response)
            print(response_hex_str)
            self.waiting_for_response = False
            raise TimeoutError("Timeout while waiting for SCPI response.")
        except OSError as e:
            self.disconnect()
            raise e
        self.waiting_for_response = False
        return response

    def receive_data(self, show_progress: bool = False) -> Data:
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
        length = struct.unpack("<I", length_buffer)[0] + 8  # Wtf are these 8

        received = 0
        data_buffer = bytearray(length)
        progress_bar = tqdm(total=length, unit="B", unit_scale=True, disable=not show_progress)
        try:
            while received < length:
                received += self.sock.recv_into(memoryview(data_buffer)[received:])
                progress_bar.update(received - progress_bar.n)
            progress_bar.close()
        except OSError as e:
            self.disconnect()
            raise e
        data = Data(bytes(data_buffer))
        self.waiting_for_response = False
        return data

    def get_bmp(self, show_progress: bool = False) -> BMP:
        """Get the BMP screenshot from the oscilloscope.

        Returns
        -------
        BMP
            The interpreted BMP data.
        """
        self.send_scpi_command(cm.GET_BMP)
        data = self.receive_data(show_progress=show_progress)
        bmp = BMP(data)
        return bmp

    def get_waveform(self, show_progress: bool = False) -> Waveform:
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

    def generate_simul_waveform(self) -> Waveform:
        """Generate a simulated waveform for testing purposes.

        Returns
        -------
        Waveform
            The simulated waveform data.
        """
        return Waveform(None, simulate=True)

    def get_deep_waveform(self, memdepth=None, show_progress: bool = False) -> Waveform:
        """Get the deep waveform data from the oscilloscope.

        Parameters
        ----------
        memdepth : str
            The memory depth to use. One of '1K', '10K', '100K', '1M', '10M'.
            Although only '10K', '1M' and '10M' seem to work.
            If None, the current memory depth is used.

        Returns
        -------
        Waveform
            The interpreted deep waveform data.
        """
        if memdepth is not None:
            self.set_memdepth(memdepth)
        selected_depth = self.get_memdepth()
        self.send_scpi_command(cm.GET_DEEP_WAVEFORM)
        data = self.receive_data(show_progress=show_progress)
        wf = Waveform(data, memdepth=selected_depth)
        return wf

    def set_ip_configuration(self, ip="192.168.1.72", port=3000, subnet="255.255.255.0", gateway="192.168.1.1"):
        """Set the IP configuration of the oscilloscope.

        Sniffed Hexstr
        --------------
        3a4d000000134d4e54ac17a74700000bb8c0a80101ffffff00

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
        cmd = hexstr("MNT") + cm.network(ip, port, gateway, subnet)
        self.send_modify_command(cmd)

    def set_trigger_configuration(
        self,
        coupling="DC",
        mode="AUTO",
        slope="RISING",
        level=0,
        channel=1,
        type="SINGLE",
    ):
        """Set the trigger configuration of the oscilloscope.

        Sniffed Hexstr
        --------------
        3a4d0000002e4d545273006502004d545273006503004d545273006504000000014d545273006505004d54527300650600000000


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

        repeating = hexstr("MTR") + cm.TRIGGER_TYPE[type] + cm.CHANNEL[channel] + hexstr("e")
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

    def set_channel_on(
        self,
        channel: int,
        coupling: str = "DC",
        voltbase: float = 1.0,
        offset: int = 0,
        proberate: int = 1,
        invert: bool = False,
        b: int = 0,
    ):
        """Turn on a channel with the given settings."""
        if channel not in cm.CHANNEL:
            raise ValueError(f"Invalid channel. Must be one of {list(cm.CHANNEL.keys())}.")
        if coupling not in cm.CHANNEL_COUPLING:
            raise ValueError(f"Invalid coupling mode. Must be one of {list(cm.CHANNEL_COUPLING.keys())}.")
        if voltbase not in cm.VOLTBASE:
            raise ValueError(f"Invalid voltbase. Must be one of {list(cm.VOLTBASE.keys())}.")
        if proberate not in cm.PROBERATE:
            raise ValueError(f"Invalid proberate. Must be one of {list(cm.PROBERATE.keys())}.")
        cmd = hexstr("MCH") + cm.CHANNEL[channel] + hexstr("o") + "01"
        cmd += cm.channel_coupling(channel, coupling)
        cmd += cm.channel_voltbase(channel, voltbase)
        cmd += cm.channel_offset(channel, offset)
        cmd += cm.channel_proberate(channel, proberate)
        cmd += cm.channel_invert(channel, invert)
        cmd += cm.channel_b(channel, b)
        self.send_modify_command(cmd)

    def set_channel_off(self, channel: int):
        """Turn off a channel."""
        if channel not in cm.CHANNEL:
            raise ValueError(f"Invalid channel. Must be one of {list(cm.CHANNEL.keys())}.")
        cmd = hexstr("MCH") + cm.CHANNEL[channel] + hexstr("o") + "00"
        self.send_modify_command(cmd)

    def set_channel_parameter(self, channel: int, parameter: str, value):
        if parameter not in cm.CHANNEL_PARAMS:
            raise ValueError(f"Invalid channel parameter. Must be one of {list(cm.CHANNEL_PARAMS.keys())}.")
        cmd = cm.CHANNEL_PARAMS[parameter](channel, value)
        self.send_modify_command(cmd)



    def set_timebase(self, timebase: float):
        """Set the timebase of the oscilloscope.

        Parameters
        ----------
        timebase : float
            The timebase in microseconds.
        """
        if timebase not in cm.TIMEBASE:
            raise ValueError(f"Invalid timebase. Must be one of {list(cm.TIMEBASE.keys())}.")

        cmd = hexstr("MHR") + hexstr('b') + cm.TIMEBASE[timebase]
        self.send_modify_command(cmd)

    def set_trigger_position(self, position: float):
        """Set the trigger position of the oscilloscope.

        Parameters
        ----------
        position : float
            The trigger position in 1/50 divs.
        """
        position_bytes = struct.pack("<i", position).hex()
        cmd = hexstr("MHR") + hexstr('v') + position_bytes
        self.send_modify_command(cmd)

    def set_memdepth(self, depth: str):
        """Set the memory depth of the oscilloscope.

        Parameters
        ----------
        depth : str
            The memory depth. One of '1K', '10K', '100K', '1M', '10M'
        """
        if depth not in cm.MEMDEPTH:
            raise ValueError(f"Invalid memory depth. Must be one of {list(cm.MEMDEPTH.keys())}.")
        if depth not in cm.VALID_MEMDEPTH:
            print(f"Warning: Memory depth {depth} might not work properly. Recommended depths are {cm.VALID_MEMDEPTH}.")

        self.send_scpi_command(f":ACQuire:MDEPth {depth}")

    def get_memdepth(self) -> str:
        """Get the current memory depth of the oscilloscope.

        Returns
        -------
        depth : str
            The current memory depth.
        """
        self.send_scpi_command(":ACQuire:MDEPth?")
        response = self.receive_scpi_response()
        if response not in cm.RESPONSE_MEMDEPTH:
            raise ValueError(f"Received invalid memory depth: {response}")
        return response

    def reboot(self):
        """Reboot the oscilloscope."""
        self.send_scpi_command(cm.REBOOT)

    def autoset(self):
        """Perform an autoset on the oscilloscope."""
        self.send_scpi_command(cm.AUTOSET)

    def force_trigger(self):
        """Force a trigger on the oscilloscope."""
        self.send_scpi_command(cm.FORCE_TRIGGER)

    def set_trigger_lvl_0(self):
        """Set the trigger level to 0V."""
        self.send_scpi_command(cm.TRIGGER_LVL_0)

    def set_trigger_lvl_50(self):
        """Set the trigger level to 50%."""
        self.send_scpi_command(cm.TRIGGER_LVL_50)


def hexstr(ascii):
    return ascii.encode("ASCII").hex()


def ascii(hexstr):
    return bytes.fromhex(hexstr).decode("ASCII")
