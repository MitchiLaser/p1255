from . import constants
import ipaddress
import socket
import struct
import math

class P1255:
    def __init__(self):
        self.sock = None
    
    def connect(self, address, port=3000):
        """Connect to the P1255 oscilloscope at the specified address and port."""
        if not isinstance(address, ipaddress.IPv4Address):
            raise ValueError(f"Not a valid IPv4 address: {str(address)}")

        # Validate port
        if not isinstance(port, int) or not (0 < port < 65536):
            raise ValueError(f"Not a valid port number, must be in between 0 and 65534: {str(port)}")

        # Create a TCP/IPv4 Socket
        self.sock = socket.socket(
            socket.AF_INET,  # Address family: IPv4
            socket.SOCK_STREAM,  # Socket type: TCP
        )
        

        # Connect to the client device
        self.sock.connect((str(address), port))
        
    def capture(self):
        if self.sock is None:
            return None
        # Send command to start streaming of binary data
        self.sock.send(b"STARTBIN")
        # use a dumb blocking socket
        # This makes implementation easier but performance might
        # be comparable to my grandma sending a fax over her 56k modem
        self.sock.setblocking(True)

        # First information that is sent is the length of the dataset
        # This information is send as a 2 bytes integer, unsigned short little endian (<H)
        read = self.sock.recv_into(payload := bytearray(2), 2)
        if read != 2:  # make sure we read 2 bytes
            raise RuntimeError("Length of dataset is not valid")
        # calculate the total length of the whole dataset
        # I don't know why but the length of the dataset is 12 bytes longer than the length of the payload
        # This was figured out by trial and error
        length = struct.unpack("<H", payload)[0] + constants.LEN_UNKNOWN

        # create the buffer to store the whole dataset
        buffer = bytearray(length)
        buffer[:2] = payload  # keep the length information in the buffer

        # read the rest of the dataset
        while read < length:
            read += self.sock.recv_into(memoryview(buffer)[read:], length - read)  # memoryview needed to avoid copying the buffer
            
        return Dataset(buffer)
            
    def disconnect(self):
        """Disconnect from the P1255 oscilloscope."""
        if self.sock:
            self.sock.close()
            self.sock = None
        
        
        
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
                exp = math.floor(number / 3)
                mant = {0: 1, 1: 2, 2: 5}[number % 3]
                volts_per_div = mant * (10 ** exp)
                return volts_per_div * 1e-3  # convert from millivolts to volts
            self.voltscale = calc_voltscale(self.buffer[constants.CHANNEL_VOLTSCALE])

            # Voltage shift
            self.volts_offset = struct.unpack(
                '<l',
                self.buffer[constants.CHANNEL_OFFSET:constants.CHANNEL_OFFSET + 4]
            )[0]

            # Get the data points from the buffer
            # '<h' corresponds to little endian signed short, times the number of samples
            self.data = [
                (x / 128) * 5 * self.voltscale for x in  # apply this transformation to all data points.
                # The (x / 128) * 5 transforms the data into the unit on the screen,
                # the self.voltscale factor scales it to volts.
                struct.unpack(
                    '<' + 'h' * ((len(self.buffer) - constants.BEGIN_CHANNEL_DATA) // 2),  # specify data format
                    self.buffer[constants.BEGIN_CHANNEL_DATA:]  # specify the slice of the dataset
                )
            ]

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
            data = [{"name": ch.name, "timescale": ch.timescale, "data": ch.data} for ch in self.channels]
            with open(filename, 'w') as f:
                json.dump(data, f)
        elif fmt == 'csv':
            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([ch.name for ch in self.channels])
                writer.writerows(zip(*[ch.data for ch in self.channels]))
        else:
            raise ValueError("Unsupported format. Use 'csv' or 'json'.")
