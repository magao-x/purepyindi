from pprint import pprint
import sys
import time
from .client import INDIClient
from .constants import *
import json

c = None

def convert_to_json(indi_dict):
    return json.dumps(indi_dict, indent=2, sort_keys=True)

def watcher(_):
    global c
    print(convert_to_json(c.to_dict()))

def main():
    global c
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--help",
        help="show this help message and exit",
        action="store_true",
    )
    parser.add_argument(
        "--watch",
        help="Watch for updates and re-output the JSON representation",
        action="store_true",
    )
    parser.add_argument(
        "-h", "--host",
        help=f"Specify hostname to connect to (default: {DEFAULT_HOST})",
        nargs="?",
        default=DEFAULT_HOST,
    )
    parser.add_argument(
        "-p", "--port",
        help=f"Specify port to connect to (default: {DEFAULT_PORT})",
        nargs="?",
        type=int,
        default=DEFAULT_PORT,
    )
    args = parser.parse_args()
    if args.help:
        parser.print_help()
        sys.exit(1)

    c = INDIClient(args.host, args.port)
    c.start()
    while len(c.devices) == 0:
        time.sleep(1)
    print(convert_to_json(c.to_dict()))
    if args.watch:
        c.add_watcher(watcher)
        while True:
            time.sleep(1)
