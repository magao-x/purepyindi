import threading
import time
from purepyindi.client import INDIClient
from purepyindi.constants import *

c = None

def reconnection_monitor():
    global c
    c = INDIClient('localhost', 7624)
    first_start = True
    while True:
        if c.status == ConnectionStatus.ERROR or first_start:
            print("Starting connection")
            try:
                c.start()
                first_start = False
            except Exception:
                print(f"Failed to start, connection status: {c.status}")
        time.sleep(1)

t = threading.Thread(target=reconnection_monitor)
t.start()
import IPython
IPython.embed()
