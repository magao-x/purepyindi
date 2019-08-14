from purepyindi.client import INDIClient
import IPython
import logging
import time

logging.basicConfig(level=logging.DEBUG)

c = INDIClient('localhost', 7624)
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
IPython.embed()
