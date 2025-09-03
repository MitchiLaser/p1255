# Peaktech P1255

Peaktech P1255 remove data acquisition software

This software can query data from the Peaktech P1255 oscilloscope via LAN, decode and export the data. It can be installed via pip:

```bash
pip install p1255
```
and it provides two executables: `peak-view` is a GUI application to view and export data and `peak-capture` is a command line tool to grab data and save it to a file.
Use `peak-capture --help` to see all available options.

## Connection

The network configuration for the oscilloscope needs to be done on the device itself. The device does not support DHCP, so you need to set a static IP address.

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
