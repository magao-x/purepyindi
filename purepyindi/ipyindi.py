from .client import INDIClient
from .constants import *
import IPython
import logging
import time
import sys
from pprint import pprint
import traceback

def watcher(update):
    for elemname in update['property']['elements']:
        elem = update['property']['elements'][elemname]
        print(f"{update['device']}.{update['name']}.{elemname}={elem['value']} ({update['property']['state'].value})")

def main():
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--help",
        help="show this help message and exit",
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
    logging.basicConfig(level=logging.WARN)

    c = INDIClient(args.host, args.port)
    c.start()
    while len(c.devices) == 0:
        print("waiting to receive properties...")
        time.sleep(1)
    print()
    print("known properties:")
    print()
    print(c)
    print("try:")
    print()
    device_name, dev = list(c.devices.items())[0]
    property_name, prop = list(dev.properties.items())[0]
    element_name, _ = list(prop.elements.items())[0]
    print(f">>> c['{device_name}.{property_name}.{element_name}'] = 'something'")
    print()
    c.add_watcher(watcher)
    IPython.embed()
