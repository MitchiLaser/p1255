#!/usr/bin/env python3

def gui():
    from PyQt5.QtWidgets import QApplication
    import sys
    from p1255.gui import MainWindow  # TODO: Verify

    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())


def cli():
    import argparse
    from p1255 import p1255  # TODO: Verify
    import ipaddress

    parser = argparse.ArgumentParser(
        prog="P1255",
        description="Capture and decode data from a P1255 oscilloscope over LAN",
        epilog="https://github.com/MitchiLaser/p1255/"
    )
    parser.add_argument("-a", "--address", type=ipaddress.IPv4Address, required=True, help="The IPv4 address of the oscilloscope", )
    parser.add_argument("-p", "--port", type=int, default=3000, help="The port to connect to, default is 3000", )
    parser.add_argument("-o", "--output", type=str, required=True, help="Output File where the dataset is saved", )
    parser.add_argument("-f", "--format", type=str, choices=["csv", "json"], required=True, help="Storage file format", )
    args = parser.parse_args()

    scope = p1255.P1255()
    scope.connect(args.address, args.port)
    dataset = scope.capture()
    del scope

    with open(args.output, "w") as f:
        if args.format == "json":
            import json
            data = [{"name": i.name, "timescale": i.timescale, "data": i.data} for i in dataset.channels]
            f.write(json.dumps(data))
        elif args.format == "csv":
            import csv
            writer = csv.writer(f)
            writer.writerow([i.name for i in dataset.channels])
            writer.writerows(zip(*[i.data for i in dataset.channels]))
