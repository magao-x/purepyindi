import asyncio
import logging
import sys
from .eventful import AsyncINDIClient
from .constants import *
from pprint import pprint

async def watch_for_updates(update):
    pprint(update)

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
        default=DEFAULT_PORT,
    )
    args = parser.parse_args()
    if args.help:
        parser.print_help()
        sys.exit(1)
    logging.basicConfig(level=logging.WARN)

    c = AsyncINDIClient(args.host, args.port)
    c.add_async_watcher(watch_for_updates)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(c.run())
    loop.close()
