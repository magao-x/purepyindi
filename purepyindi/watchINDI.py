import logging
import time
import sys
from .client import INDIClient
from .constants import *
from . import log
from pprint import pprint

def watch_for_updates(prop, did_anything_change):
    pprint(prop.to_jsonable())

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
    parser.add_argument(
        "INDI_PROPERTY",
        help="Dotted INDI identifier deviceName.propertyName"
    )
    args = parser.parse_args()
    if args.help:
        parser.print_help()
        sys.exit(1)
    print(args)
    log.set_log_level('INFO')
    c = INDIClient(args.host, args.port)
    c.start()
    c.wait_for_properties([args.INDI_PROPERTY])
    device_name, prop_name = args.INDI_PROPERTY.split('.')
    watched_entity = c.devices[device_name].properties[prop_name]
    watched_entity.add_watcher(watch_for_updates)
    while True:
        time.sleep(1)