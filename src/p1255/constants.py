#!/usr/bin/env python3


# Orientation within the dataset
BEGIN_SERIAL_STRING = 0x16
LEN_SERIAL_STRING = 12

CHANNEL_BITMAP = 0x35

LEN_UNKNOWN = 12  # The weird 12 bits that were figured out by trial and error
LEN_HEADER = 66

BEGIN_CHANNEL_DATA = 0x3b
CHANNEL_TIMESCALE = 0x1b
CHANNEL_VOLTSCALE = 0x23
CHANNEL_OFFSET = 0x1f


CONNECTION_HELP = """P1255 Connection Help:

    - Connect the Oscilloscope to a network via a LAN cable.
    - Press the "utility" button on the oscilloscope.
    - Press the "H1" button to access the possible menus.
    - Scroll down to "LAN Set" by rotating the "M" knob.
    - Press the "M" knob to enter the menu.
    - Press on the "H2" Button ("Set").
    - You can use the "F*" buttons and the "M" knob to adjust other settings.
    - Save the changes and restart to apply them.
        """