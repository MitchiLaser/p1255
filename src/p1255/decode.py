#!/usr/bin/env pyton3

from . import constants
import math
import struct


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
