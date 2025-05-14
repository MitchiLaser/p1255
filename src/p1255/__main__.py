#!/usr/bin/env python3

import argparse
import capture
import constants
import decode
import ipaddress


def main():
    parser = argparse.ArgumentParser("P1255", description="Capture and decode data from a P1255 oscilloscope")
    parser.add_argument(
        "-a",
        "--address",
        type=ipaddress.IPv4Address,
        help="The IPv4 address of the oscilloscope",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=3000,
        help="The port to connect to, default is 3000",
    )
    args = parser.parse_args()

    # Capture the dataset from the oscilloscope
    print("Capturing dataset...")
    dataset = capture.capture(args.address, args.port)
    print("Dataset captured")
    # Decode the dataset
    print("Decoding dataset...")
    dataset = decode.Dataset(dataset)
    print("Dataset decoded")

    # TODO: Continue
    # TODO: This might be turned into a simple stand alone program that captures a dataset from the oscilloscope and stores it in a file (CSV, JSON, etc.)


if __name__ == "__main__":
    main()
