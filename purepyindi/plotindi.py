import matplotlib.pyplot as plt
from purepyindi.client import INDIClient
from purepyindi.constants import DEFAULT_HOST, DEFAULT_PORT, INDIPropertyKind
import logging
import time
import sys
import datetime

DEFAULT_MINUTES = 5

times, values, n_minutes, ax, line = None, None, None, None, None

def update_plot():
    global times, values, n_minutes, ax, line
    current_time = times[-1]
    n_minutes_ago = current_time - datetime.timedelta(minutes=n_minutes)
    plot_limits = n_minutes_ago, current_time
    line.set_data(times, values)
    ax.relim()
    ax.set_xlim(*plot_limits)
    ax.autoscale_view()
    plt.draw()
    plt.pause(0.05)

def print_and_plot_changes(element):
    global times, values
    element_name = element.name
    property_name = element.property.name
    device_name = element.property.device.name
    print(f"{device_name}.{property_name}.{element_name}={element.value}")
    current_time = datetime.datetime.now()
    times.append(current_time)
    values.append(element.value)
    update_plot()

def main():
    global times, values, n_minutes, ax, line
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
        type=int,
        default=DEFAULT_PORT,
    )
    parser.add_argument(
        "-m", "--minutes",
        help=f"Minutes of data to show (default: {DEFAULT_MINUTES})",
        nargs="?",
        type=float,
        default=DEFAULT_MINUTES,
    )
    args = parser.parse_args()
    if args.help:
        parser.print_help()
        sys.exit(1)
    logging.basicConfig(level=logging.WARN)
    n_minutes = args.minutes
    c = INDIClient(args.host, args.port)
    c.start()
    print(f"waiting to initialize {args.identifier}...", end='')
    while args.identifier not in c:
        time.sleep(1)
        print('.', end='')
    print()
    device_name, property_name, element_name = args.identifier.split('.')
    the_property = c.devices[device_name].properties[property_name]
    if the_property.KIND != INDIPropertyKind.NUMBER:
        raise RuntimeError(
            f"{args.identifier} is not of kind 'INDIPropertyKind.NUMBER' (got {the_property.kind})"
        )
    elem = the_property.elements[element_name]
    print(f"Added watcher to {elem}")
    plt.ion()
    fig, ax = plt.subplots()
    ax.set_xlabel('time')
    ax.set_ylabel(args.identifier)
    times = [datetime.datetime.now()]
    values = [elem.value]
    (line,) = ax.plot_date(times, values, '-')
    elem.add_watcher(print_and_plot_changes)
    update_plot()
    plt.show(block=True)

if __name__ == "__main__":
    main()
