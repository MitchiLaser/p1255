import struct
import ipaddress


# strings to send as scpi commands
# --------------------------------
# Get Data
GET_WAVEFORM = "STARTBIN"
GET_DEEP_WAVEFORM = "STARTMEMDEPTH"
GET_BMP = "STARTBMP"

# Get Values
GET_AVERAGE = ":ACQuire:AVERage?"
GET_TYPE = ":ACQuire:TYPE?"
GET_MEMDEPTH = ":ACQuire:MDEPth?"

# Responses (since peaktech does not follow SCPI standard here to send the \n)
RESPONSE_MEMDEPTH = ["1K", "10K", "100K", "1M", "10M"]
VALID_MEMDEPTH = ["10K", "1M", "10M"]  # only these seem to work
RESPONSE_TYPE = ["PEAK", "SAMPle", "AVERage"]
RESPONSE_AVERAGE = ["4", "16", "64", "128"]

SCPI_RESPONSES = RESPONSE_MEMDEPTH + RESPONSE_TYPE + RESPONSE_AVERAGE



# For building commands
# ---------------------
CHANNEL = {1: "00", 2: "01"}
TRIGGER_COUPLING = {'DC': "00", 'AC': "01", 'HF': "02", 'LF': "03"}
TRIGGER_MODE = {'AUTO': "00", 'NORMAL': "01", 'SINGLE': "02"}
TRIGGER_SLOPE = {'RISING': "00", 'FALLING': "01"}
TRIGGER_TYPE = {'SINGLE': 's'.encode('ASCII').hex(),
                'ALTERNATE': 'a'.encode('ASCII').hex()}
PROBERATE = {1: "00", 10: "01", 100: "02", 1000: "03"}
CHANNEL_COUPLING = {'DC': "00", 'AC': "01", 'GND': "02"}
VOLTBASE = { # in V/div
          .002: "00",
          .005: "01",
          .010: "02",
          .020: "03",
          .050: "04",
          .100: "05",
          .200: "06",
          .500: "07",
         1.   : "08",
         2.   : "09",
         5.   : "0A",
        10.   : "0B"
        }
VOLTBASELIST = list(VOLTBASE.keys())

TIMEBASE = { # in us/div? # from 1ns to 100s
    .001: "00", # 1ns
    .002: "01", # 2ns
    .005: "02", # 5ns
    .010: "03", # 10ns
    .020: "04", # 20ns
    .050: "05", # 50 ns
    .100: "06", # 100ns
    .200: "07", # 200ns
    .500: "08", # 500ns
    1.   : "09", # 1us
    2.   : "0A", # 2us
    5.   : "0B", # 5us
    10.  : "0C", # 10us
    20.  : "0D", # 20us
    50.  : "0E", # 50us
    100. : "0F", # 100us
    500. : "10", # 500us
    1000.: "11", # 1ms
    2000.: "12", # 2ms
    5000.: "13", # 5ms
    10000.: "14", # 10ms
    20000.: "15", # 20ms
    50000.: "16", # 50ms
    100000.: "17", # 100ms
    200000.: "18", # 200ms
    500000.: "19", # 500ms
    1000000.: "1A", # 1s
    2000000.: "1B", # 2s
    5000000.: "1C", # 5s
    10000000.: "1D", # 10s
    20000000.: "1E", # 20s
    50000000.: "1F", # 50s
    100000000.: "20" # 100s
}
TIMEBASELIST = list(TIMEBASE.keys())


def channel_coupling(channel: int, coupling: str) -> str:
    """Convert channel coupling settings to the corresponding hex string.
    
    Parameters
    ----------
    channel : int
        The channel number.
    coupling : str
        The coupling type ('DC', 'AC', 'GND').
        
    Returns
    -------
    str
        The corresponding hex string for the channel coupling.
    """
    if channel not in CHANNEL:
        raise ValueError(f"Channel must be one of {list(CHANNEL.keys())}.")
    if coupling not in CHANNEL_COUPLING:
        raise ValueError(f"Coupling must be one of {list(CHANNEL_COUPLING.keys())}.")
    
    return hexstr("MCH") + CHANNEL[channel] + hexstr("c") + CHANNEL_COUPLING[coupling]

def channel_voltbase(channel: int, voltbase: float) -> str:
    """Convert channel voltage base settings to the corresponding hex string.
    
    Parameters
    ----------
    channel : int
        The channel number.
    voltbase : float
        The voltage base in volts per division.
        
    Returns
    -------
    str
        The corresponding hex string for the channel voltage base.
    """
    if channel not in CHANNEL:
        raise ValueError(f"Channel must be one of {list(CHANNEL.keys())}.")
    if voltbase not in VOLTBASE:
        raise ValueError(f"Voltbase must be one of {list(VOLTBASE.keys())}.")
    
    return hexstr("MCH") + CHANNEL[channel] + hexstr("v") + VOLTBASE[voltbase]

def channel_offset(channel: int, offset: int) -> str:
    """Convert channel offset settings to the corresponding hex string.
    
    Parameters
    ----------
    channel : int
        The channel number.
    offset : int
        The offset in 1/25 of a division
        
    Returns
    -------
    str
        The corresponding hex string for the channel offset.
    """
    if channel not in CHANNEL:
        raise ValueError(f"Channel must be one of {list(CHANNEL.keys())}.")
    return hexstr("MCH") + CHANNEL[channel] + hexstr("o") + struct.pack(">i", offset).hex()

def channel_proberate(channel: int, proberate: int) -> str:
    """Convert channel probe rate settings to the corresponding hex string.
    
    Parameters
    ----------
    channel : int
        The channel number.
    proberate : int
        The probe rate
        
    Returns
    -------
    str
        The corresponding hex string for the channel probe rate.
    """
    if channel not in CHANNEL:
        raise ValueError(f"Channel must be one of {list(CHANNEL.keys())}.")
    if proberate not in PROBERATE:
        raise ValueError(f"Proberate must be one of {list(PROBERATE.keys())}.")
    
    return hexstr("MCH") + CHANNEL[channel] + hexstr("p") + PROBERATE[proberate]

def channel_invert(channel: int, invert: bool) -> str:
    """Convert channel invert settings to the corresponding hex string.
    
    Parameters
    ----------
    channel : int
        The channel number.
    invert : bool
        Whether to invert the channel (True) or not (False).
        
    Returns
    -------
    str
        The corresponding hex string for the channel invert setting.
    """
    if channel not in CHANNEL:
        raise ValueError(f"Channel must be one of {list(CHANNEL.keys())}.")
    inv = "01" if invert else "00"
    return hexstr("MCH") + CHANNEL[channel] + hexstr("i") + inv

def channel_b(channel: int, b: int) -> str:
    """Convert channel B settings to the corresponding hex string.
    
    Parameters
    ----------
    channel : int
        The channel number.
    b : int
        Dont know what this does
        
    Returns
    -------
    str
        The corresponding hex string for the channel B setting.
    """
    if channel not in CHANNEL:
        raise ValueError(f"Channel must be one of {list(CHANNEL.keys())}.")
    return hexstr("MCH") + CHANNEL[channel] + hexstr("b") + struct.pack(">i", b).hex()

CHANNEL_PARAMS = {
    'coupling': channel_coupling,
    'voltbase': channel_voltbase,
    'offset': channel_offset,
    'proberate': channel_proberate,
    'invert': channel_invert,
    'b': channel_b
}


def trigger_voltage(voltage: float) -> str:
    """Convert a trigger voltage to the corresponding hex string.
    
    TODO it might be that it has to be set in 1/25 of a division
    
    Trigger Voltages can be set in steps of 40mV from -7V to +5V.
    The entered voltage is rounded to the nearest valid value.
    
    Parameters
    ----------
    voltage : float
        The trigger voltage in volts.
        
    Returns
    -------
    str
        The corresponding hex string for the trigger voltage.
    """
    if voltage < -7:
        voltage = -7
    elif voltage > 5:
        voltage = 5
    steps = round(voltage / 0.04)
    hex_str = struct.pack(">i", steps).hex()
    return hex_str

def network(ip: str, port: int, gateway: str, mask: str) -> str:
    """Convert network settings to the corresponding hex string.
    
    Parameters
    ----------
    ip : str
        The IP address in dotted decimal notation.
    port : int
        The port number (0..65535) although maybe only (0..4000)
    gateway : str
        The gateway address in dotted decimal notation.
    mask : str
        The subnet mask in dotted decimal notation.
        
    Returns
    -------
    str
        The corresponding hex string for the network settings.
    """
    try:
        ip = ipaddress.IPv4Address(ip)
        gateway = ipaddress.IPv4Address(gateway)
        mask = ipaddress.IPv4Address(mask)
    except ipaddress.AddressValueError as e:
        raise ValueError(f"Invalid IP address: {e}")

    if not (0 <= port <= 65535):
        raise ValueError("Port must be between 0 and 65535.")
    
    ip = ip.packed.hex()
    gateway = gateway.packed.hex()
    mask = mask.packed.hex()
    
    port = port.to_bytes(4, byteorder='big').hex()

    return ip + port + mask + gateway


def hexstr(ascii):
    return ascii.encode("ASCII").hex()