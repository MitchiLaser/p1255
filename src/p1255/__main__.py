#!/usr/bin/env python3

import argparse
from . import capture
from . import decode
import ipaddress


def main():
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

    dataset = capture.capture(args.address, args.port)
    dataset = decode.Dataset(dataset)

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


if __name__ == "__main__":
    main()
