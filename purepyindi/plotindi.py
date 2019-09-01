import matplotlib.pyplot as plt
from purepyindi.client import INDIClient
from purepyindi.constants import DEFAULT_HOST, DEFAULT_PORT, INDIPropertyKind
import logging
import time
import sys
import datetime

times, values = None, None

def print_changes(element):
    global times, values
    element_name = element.name
    property_name = element.property.name
    device_name = element.property.device.name
    print(f"{device_name}.{property_name}.{element_name}={element.value}")
    times.append(datetime.datetime.now())
    values.append(element.value)
    plt.gca().lines[0].set_xdata(times)
    plt.gca().lines[0].set_ydata(values)
    plt.gca().relim()
    plt.gca().autoscale_view()
    plt.pause(0.05)

def main():
    global times, values
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--help",
        help="show this help message and exit",
        action="store_true",
    )
    parser.add_argument("identifier", help="INDI identifier (device.property.element)")
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
    c = INDIClient(args.host, args.port)
    c.start()
    print(f"waiting to initialize {args.identifier}...", end='')
    while args.identifier not in c:
        time.sleep(1)
        print('.')
    print()
    device_name, property_name, element_name = args.identifier.split('.')
    the_property = c.devices[device_name].properties[property_name]
    if the_property.KIND != INDIPropertyKind.NUMBER:
        raise RuntimeError(
            f"{args.identifier} is not of kind 'INDIPropertyKind.NUMBER' (got {the_property.kind})"
        )
    elem = the_property.elements[element_name]
    elem.add_watcher(print_changes)
    print(f"Added watcher to {elem}")
    plt.ion()
    plt.xlabel('time')
    plt.ylabel(args.identifier)
    times = [datetime.datetime.now()]
    values = [elem.value]
    plt.plot_date(times, values, '-')
    plt.show(block=True)

if __name__ == "__main__":
    main()
