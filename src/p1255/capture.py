#!/usr/bin/env pyton3

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
        raise ValueError("address must be an IPv4 address")

    # Validate port
    if not isinstance(port, int) or not (0 < port < 65536):
        raise ValueError("port must be an integer between 0 and 65535")

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

    # Create a first buffer to store the payload length
    payload = bytearray(2)

    # First information that is sent is the length of the dataset
    # This information is send as a 2 bytes integer, unsigned short little endian (<H)
    read = sock.recv_into(payload, 2)
    if read != 2:  # make sure we read 2 bytes
        raise RuntimeError("Length of dataset is not valid")
    # calculate the total length of the whole dataset
    length = struct.unpack("<H", payload)[0] + 12  # The 12 bytes = 2 bytes length information + 10 bytes header

    # create the buffer to store the whole dataset
    buffer = bytearray(length)
    buffer[:2] = payload  # keep the length information in the buffer

    # read the rest of the dataset
    while read < length:
        read += sock.recv_into(memoryview(buffer)[read:], length - read)  # memoryview needed to avoid copying the buffer

    sock.close()
    return buffer
