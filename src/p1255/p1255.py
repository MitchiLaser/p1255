from . import constants
import ipaddress
import socket
import struct
import math
import numpy as np
import hexdump


class P1255:
    def __init__(self):
        self.sock = None

    def connect(self, address, port=3000):
        """Connect to the P1255 oscilloscope at the specified address and port."""
        if not isinstance(address, ipaddress.IPv4Address):
            try:
                address = ipaddress.IPv4Address(address)
            except ipaddress.AddressValueError:
                raise ValueError(f"Not a valid IPv4 address: {str(address)}")

        # Validate port
        if not isinstance(port, int) or not (0 < port < 65536):
            raise ValueError(f"Not a valid port number, must be in between 0 and 65534: {str(port)}")

        # Create a TCP/IPv4 Socket
        self.sock = socket.socket(
            socket.AF_INET,  # Address family: IPv4
            socket.SOCK_STREAM,  # Socket type: TCP
        )

        self.sock.settimeout(1)  # 1 second timeout
        # Connect to the client device
        try:
            self.sock.connect((str(address), port))
        except Exception as e:
            self.sock.close()
            self.sock = None
            raise e
        
        # self.send_command(":SDSLVER#") # ???
        # self.send_command(":SDSLSCPI#") # start the SCPI port
        
        
        return True

    def capture(self):
        if self.sock is None:
            return None
        try:
            # Send command to start streaming of binary data
            self.sock.send(b"STARTBIN")
            self.sock.settimeout(1)  # 1 second timeout

            # First information that is sent is the length of the dataset
            read = self.sock.recv_into(payload := bytearray(2), 2)
            if read != 2:
                raise RuntimeError("Length of dataset is not valid")
            length = struct.unpack("<H", payload)[0] + constants.LEN_UNKNOWN

            buffer = bytearray(length)
            buffer[:2] = payload

            while read < length:
                n = self.sock.recv_into(memoryview(buffer)[read:], length - read)
                if n == 0:
                    raise ConnectionError("Socket connection lost during data capture.")
                read += n

            return Dataset(buffer)
        except (TimeoutError, ConnectionError) as e:
            raise ConnectionError(f"Socket error during capture: {e}")
        
        
        
        
    def set_trigger_configuration(
        self,
        coupling = "DC",
        mode = "AUTO",
        flank = "RISING",
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
        flank : str
            The trigger flank. One of 'RISING', 'FALLING'
        level : int
            The trigger level in Volts. Range is +5V to -7V in steps of 40mV. (Will be rounded to nearest step)
        channel : int
            The channel to trigger on. 1 or 2
        type : str
            The trigger type. 'SINGLE' or 'ALTERNATE'
        """
        TRIGGER_TYPE_MAP_ASCII = {
            'SINGLE': 's',
            'ALTERNATE': 'a'
        }
        CHANNEL_MAP = {
            1: '00',
            2: '01'
        }
        COUPLING_MAP = {
            'DC': '00',
            'AC': '01',
            'HF': '02',
            'LF': '03'
        }
        MODE_MAP = {
            'AUTO': '00',
            'NORM': '01',
            'SINGLE': '02'
        }
        FLANK_MAP = {
            'RISING': '00',
            'FALLING': '01'
        }
        if coupling not in COUPLING_MAP:
            raise ValueError(f"Invalid coupling mode. Must be one of {list(COUPLING_MAP.keys())}.")
        if mode not in MODE_MAP:
            raise ValueError(f"Invalid trigger mode. Must be one of {list(MODE_MAP.keys())}.")
        if flank not in FLANK_MAP:
            raise ValueError(f"Invalid trigger flank. Must be one of {list(FLANK_MAP.keys())}.")
        if channel not in CHANNEL_MAP:
            raise ValueError(f"Invalid channel. Must be one of {list(CHANNEL_MAP.keys())}.")
        if type not in TRIGGER_TYPE_MAP_ASCII:
            raise ValueError(f"Invalid trigger type. Must be one of {list(TRIGGER_TYPE_MAP_ASCII.keys())}.")
        if not (-7.0 <= level <= 5.0):
            raise ValueError("Invalid trigger level. Must be between -7V and +5V.")
        
        cmd = Command()
        cmd += ":M"
        cmd.add_hex("0000002e")
        
        # Get the repeating string
        repeat = Command()
        repeat += "MTR"
        repeat += TRIGGER_TYPE_MAP_ASCII[type]
        repeat.add_hex(CHANNEL_MAP[channel])
        
        # Coupling
        cmd += repeat
        cmd.add_hex("02")
        cmd.add_hex(COUPLING_MAP[coupling])
        
        # Mode
        cmd += repeat
        cmd.add_hex("03")
        cmd.add_hex(MODE_MAP[mode])
    
        # Dont know
        cmd += repeat
        cmd.add_hex("04")
        cmd.add_hex("00000000")
        
        # Flank
        cmd += repeat
        cmd.add_hex("05")
        cmd.add_hex(FLANK_MAP[flank])
        
        # Level
        cmd += repeat
        cmd.add_hex("06")
        trigger_level_steps = round(level / 0.04)  # nearest integer
        trigger_level_steps = max(-2**31, min(trigger_level_steps, 2**31 - 1))  # clamp to signed 32-bit range
        b = struct.pack(">i", trigger_level_steps)  # pack into 4 bytes, big-endian signed int
        hex_level = b.hex()
        cmd.add_hex(hex_level)
        cmd.send(self)
        
    def set_fourier_configuration():
        """
        
        :M....MFT
        1byte o-> on/off?
        1byte f-> frequency?
        1byte s
        1byte w-> window?
        2byte a
        1byte z->Zoom?
        
        """
        pass
    

    def set_channel_configuration(
        self,
        channel: int,
        probe_rate: int = 1,
        coupling: str = "DC",
        voltbase_V: float = 0,
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
        CHANNEL_MAP = {
            1: "00",
            2: "01"
        }
        PROBERATE_MAP = {
            1: "00",
            10: "01",
            100: "02",
            1000: "03"
        }
        COUPLING_MAP = {
            'DC': "00",
            'AC': "01",
            'GND': "02"
        }
        VOLTBASE_MAP = {
        0.002: "00",
        0.005: "01",
        0.010: "02",
        0.020: "03",
        0.050: "04",
        0.100: "05",
        0.200: "06",
        0.500: "07",
        1.000: "08",
        2.000: "09",
        5.000: "0A",
        10.000: "0B"
        }
        
        if channel not in CHANNEL_MAP:
            raise ValueError(f"Invalid channel. Must be one of {list(CHANNEL_MAP.keys())}.")
        if probe_rate not in PROBERATE_MAP:
            raise ValueError(f"Invalid probe rate. Must be one of {list(PROBERATE_MAP.keys())}.")
        if coupling not in COUPLING_MAP:
            raise ValueError(f"Invalid coupling mode. Must be one of {list(COUPLING_MAP.keys())}.")
        if voltbase_V not in VOLTBASE_MAP:
            raise ValueError(f"Invalid voltbase. Must be one of {list(VOLTBASE_MAP.keys())}.")
        
        cmd = Command()
        cmd += ":M"
        cmd.add_hex("00000006") # length of the command
        cmd += "MCH"
        # Channel
        cmd.add_hex(CHANNEL_MAP[channel])
        # Prope rate
        cmd += "p"
        cmd.add_hex(PROBERATE_MAP[probe_rate])
        # Coupling
        cmd += "c"
        cmd.add_hex(COUPLING_MAP[coupling])
        # Voltbase
        cmd += "v"
        cmd.add_hex(VOLTBASE_MAP[voltbase_V])
        cmd.send(self)
        

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
        if self.sock is None:
            return None

        try:
            ip_addr = ipaddress.IPv4Address(ip)
            subnet_addr = ipaddress.IPv4Address(subnet)
            gateway_addr = ipaddress.IPv4Address(gateway)
        except ipaddress.AddressValueError as e:
            raise ValueError(f"Invalid IP address: {e}")

        if not (0 < port <= 4000):
            raise ValueError(f"Port number must be between 1 and 4000: {port}")

        # Construct the command
        cmd = Command()
        cmd += ":M"
        cmd.add_hex("00000013")  # length of the command
        cmd += "MNT"
        cmd.add_hex(ip_addr.packed.hex())
        cmd.add_hex(port.to_bytes(4, byteorder="big").hex())
        cmd.add_hex(subnet_addr.packed.hex())
        cmd.add_hex(gateway_addr.packed.hex())
        cmd.send(self)

    

    def disconnect(self):
        """Disconnect from the P1255 oscilloscope."""
        if self.sock:
            self.sock.close()
            self.sock = None

    def __del__(self):
        self.disconnect()


class Dataset:

    class Channel:
        def __init__(self, buffer: memoryview) -> None:
            self.buffer = buffer

            # Channel name
            self.name = str(buffer[:3], 'utf8')

            # Timescale information
            # How long is the timescale in which the total channel data was captured
            def calc_timescale(number):
                exp = math.floor(number / 3)
                mant = {0: 1, 1: 2, 2: 5}[number % 3]
                time_per_div = mant * (10 ** exp)
                return 15 * time_per_div * 1e-9  # times 15 divisions on the screen, convert from nanoseconds to seconds
            self.timescale = calc_timescale(self.buffer[constants.CHANNEL_TIMESCALE])

            # Voltage scaling information
            def calc_voltscale(number):
                number += 4
                exp = math.floor(number / 3) - 1  # dont know why -1
                mant = {0: 1, 1: 2, 2: 5}[number % 3]
                volts_per_div = mant * (10 ** exp)
                return volts_per_div * 1e-3  # convert from millivolts to volts
            self.voltscale = calc_voltscale(self.buffer[constants.CHANNEL_VOLTSCALE])

            # Voltage shift # Julian: I think this is the offset in 1/25 of a div.
            self.volts_offset = struct.unpack(
                '<l',
                self.buffer[constants.CHANNEL_OFFSET:constants.CHANNEL_OFFSET + 4]
            )[0]

            # Get the data points from the buffer
            # '<h' corresponds to little endian signed short, times the number of samples
            self.data = np.array([
                (x / 128) * 5 * self.voltscale for x in  # apply this transformation to all data points.
                # The (x / 128) * 5 transforms the data into the unit on the screen,
                # the self.voltscale factor scales it to volts.
                struct.unpack(
                    '<' + 'h' * ((len(self.buffer) - constants.BEGIN_CHANNEL_DATA) // 2),  # specify data format
                    self.buffer[constants.BEGIN_CHANNEL_DATA:]  # specify the slice of the dataset
                )
            ])

            self.data_divisions = self.data / self.voltscale + self.volts_offset / 25

    def __init__(self, buffer: bytearray) -> None:
        self._buffer = buffer
        self.channels = list()

        # The model name and serial number of the oscilloscope
        # starts at 0x16 and is 12 bytes long
        # first 5 digits are the model name, the rest is the serial number
        serial_raw = buffer[constants.BEGIN_SERIAL_STRING:constants.BEGIN_SERIAL_STRING + constants.LEN_SERIAL_STRING]
        self.model, self.serial = str(serial_raw[:5], 'utf8'), str(serial_raw[6:], 'utf8')

        # Number of channels in dataset = number of set bits in byte 0x35
        num_channels = buffer[constants.CHANNEL_BITMAP].bit_count()

        # Get the length of the dataset but
        # remove the 12 additional bits from the length of the dataset
        # Calculate the region of each channel
        channel_data_size = (len(buffer) - constants.LEN_HEADER) // num_channels

        for ch in range(num_channels):
            # Get a slice of the dataset and let the channel class do its work
            # The slices first have an offset (header) and then they are concatenated
            # Append this to the list of channels
            self.channels.append(
                Dataset.Channel(
                    memoryview(buffer)[constants.LEN_HEADER + ch * channel_data_size:constants.LEN_HEADER + (ch + 1) * channel_data_size]
                )
            )

    def save(self, filename, fmt='csv'):
        """Save the dataset to a file in the specified format."""
        if fmt == 'json':
            import json
            data = [{"name": ch.name, "timescale": ch.timescale, "data": ch.data.tolist()} for ch in self.channels]
            with open(filename, 'w') as f:
                json.dump(data, f)
        elif fmt == 'csv':
            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Time (s)'] + [f"{ch.name} (V)" for ch in self.channels])  # write header
                # Calculate timescale information
                time = np.linspace(start=(-1) * self.channels[0].timescale / 2, stop=self.channels[0].timescale / 2, num=len(self.channels[0].data), endpoint=True)
                # write the data with the time column
                write_data = [time] + [ch.data for ch in self.channels]
                writer.writerows(zip(*write_data))
        elif fmt == 'npz':
            data = {
                **{ch.name: ch.data for ch in self.channels},
                'time': np.linspace(start=(-1) * self.channels[0].timescale / 2, stop=self.channels[0].timescale / 2, num=len(self.channels[0].data), endpoint=True)
            }
            np.savez(filename, **data)  # save as .npz file
        else:
            raise ValueError("Unsupported format. Use 'csv', 'json' or 'npz'.")




def ascii_to_hex_str(ascii_str: str) -> str:
    """Convert an ASCII string to a hex string."""
    hex_string = ascii_str.encode("ASCII").hex()
    return hex_string

class Command:
    def __init__(self):
        self._hex = ""
    
    def add_hex(self, hex_str: str):
        """Add a hex string to the command."""
        self._hex += hex_str
        return self
    
    def add_ascii(self, ascii_str: str):
        """Add an ASCII string to the command."""
        self._hex += ascii_to_hex_str(ascii_str)
        return self
    
    def __add__(self, other):
        if isinstance(other, Command):
            return Command().add_hex(self._hex + other._hex)
        elif isinstance(other, str):
            return Command().add_hex(self._hex + ascii_to_hex_str(other))
        else:
            raise TypeError("Can only add Command or str to Command")
        
    def dump(self):
        """Dump the command as a hex dump."""
        hexdump.hexdump(bytes.fromhex(self._hex))

    def get_bytes(self):
        """Get the command as bytes."""
        return bytes.fromhex(self._hex)
    
    def send(self, p1255: P1255):
        """Send the command to the P1255."""
        if p1255.sock is None:
            self.dump()
        else:
            p1255.sock.sendall(self.get_bytes())