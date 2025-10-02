import math
import struct
import ipaddress

GET_WAVEFORM = "STARTBIN"
GET_DEEP_WAVEFORM = "STARTMEMDEPTH"
GET_BMP = "STARTBMP"

CHANNEL = {1: "00", 2: "01"}
TRIGGER_COUPLING = {'DC': "00", 'AC': "01", 'HF': "02", 'LF': "03"}
TRIGGER_MODE = {'Auto': "00", 'Normal': "01", 'Single': "02"}
TRIGGER_SLOPE = {'Rising': "00", 'Falling': "01"}
TRIGGER_TYPE = {'SINGLE': 's'.encode('ASCII').hex(),
                'ALTERNATE': 'a'.encode('ASCII').hex()}
PROBERATE = {1: "00", 10: "01", 100: "02", 1000: "03"}
CHANNEL_COUPLING = {'DC': "00", 'AC': "01", 'GND': "02"}
VOLTBASE = {
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

def calc_timescale(number):
    exp = math.floor(number / 3)
    mant = {0: 1, 1: 2, 2: 5}[number % 3]
    time_per_div = mant * (10 ** exp)
    return 15 * time_per_div * 1e-9  # times 15 divisions on the screen, convert from nanoseconds to seconds


def trigger_voltage(voltage: float) -> str:
    """Convert a trigger voltage to the corresponding hex string.
    
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