#!/usr/bin/env python3
from p1255.constants import CONNECTION_HELP
import argparse


def gui():
    from PyQt5.QtWidgets import QApplication
    import sys
    from p1255.gui import MainWindow  # TODO: Verify

    parser = argparse.ArgumentParser(
        prog="P1255",
        description="Capture and decode data from a P1255 oscilloscope over LAN\n\n" + CONNECTION_HELP,
        epilog="https://github.com/MitchiLaser/p1255/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-c", "--customIP", action="store_true", help="Shows the custom IP selection even when alias file was found.")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = MainWindow(disable_aliases=args.customIP)
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())


def cli():
    from p1255 import p1255  # TODO: Verify
    import ipaddress

    parser = argparse.ArgumentParser(
        prog="P1255",
        description="Capture and decode data from a P1255 oscilloscope over LAN\n\n" + CONNECTION_HELP,
        epilog="https://github.com/MitchiLaser/p1255/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-a", "--address", type=ipaddress.IPv4Address, required=True, help="The IPv4 address of the oscilloscope", )
    parser.add_argument("-p", "--port", type=int, default=3000, help="The port to connect to, default is 3000", )
    parser.add_argument("-o", "--output", type=str, required=True, help="Output File where the dataset is saved", )
    parser.add_argument("-f", "--format", type=str, default="csv", choices=["csv", "json", "npz"], help="Storage file format", )
    args = parser.parse_args()

    scope = p1255.P1255()
    scope.connect(args.address, args.port)
    dataset = scope.capture()
    dataset.save(args.output, args.format)
    del scope
