#!/usr/bin/env pyton3

from . import constants
import ipaddress
import socket
import struct


def capture(address: ipaddress.IPv4Address, port: int = 3000) -> bytearray:
    """
    Parameters
    ----------
    address : ipaddress.IPv4Address
        the IPv4 Address of the device to connect to
    port : int
        the port to connect to, default is 3000

    Returns
    -------
    bytearray
        the dataset received from the device

    Raises
    ------
    ValueError :
        if the address is not a valid IPv4 address
        if the port is not a valid port number

    RuntimeError :
        if the length of the dataset received from the device is not valid
    """

    # Validate ip Address
    if not isinstance(address, ipaddress.IPv4Address):
        raise ValueError(f"Not a valid IPv4 address: {str(address)}")

    # Validate port
    if not isinstance(port, int) or not (0 < port < 65536):
        raise ValueError(f"Not a valid port number, must be in between 0 and 65534: {str(port)}")

    # Create a TCP/IPv4 Socket
    sock = socket.socket(
        socket.AF_INET,  # Address family: IPv4
        socket.SOCK_STREAM,  # Socket type: TCP
    )

    # Connect to the client device
    sock.connect((str(address), port))
    # Send command to start streaming of binary data
    sock.send(b"STARTBIN")
    # use a dumb blocking socket
    # This makes implementation easier but performance might
    # be comparable to my grandma sending a fax over her 56k modem
    sock.setblocking(True)

    # First information that is sent is the length of the dataset
    # This information is send as a 2 bytes integer, unsigned short little endian (<H)
    read = sock.recv_into(payload := bytearray(2), 2)
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
        read += sock.recv_into(memoryview(buffer)[read:], length - read)  # memoryview needed to avoid copying the buffer

    sock.close()
    return buffer
