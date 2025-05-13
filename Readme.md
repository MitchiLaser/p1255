# Peaktech P1255



# Documentation

This document describes all the necessary information to recreate the whole program from scratch.
It also explains how to query data from the oscilloscope and how to access the content of the .bin file

## Connection

### IPv4 LAN

The Oscilloscope is connected to a network via a LAN cable. The network interface provides an IPv4 TCP/IP socket, listening on port 3000 on the device. Unfortunately these devices do not support DHCP, so the network settings need to be done manually:
- Press the "utility" button on the oscilloscope
- Press the "H1" button to access the possible menus
- Scroll down to "LAN Set" by rotating the "M" knob
- Press the "M" knob to enter the menu
- Press on the "H2" Button ("Set")
- You can use The "F*" buttons and the "M" knob to adjust all settings in this menu.
    - I dunnot know why, but you can also set the MAC Adress to any value. Why??? Is this important because they have all the same default setting???
- Don't forget to save the changes. Restart the device to apply the changes.

### IPv6

**There is no information about IPv6 support available**
