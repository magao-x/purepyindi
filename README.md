# purepyindi

**Build status:** [![CircleCI](https://circleci.com/gh/magao-x/purepyindi.svg?style=svg)](https://circleci.com/gh/magao-x/purepyindi)

A pure Python client for [INDI](https://indilib.org/) (the Instrument Neutral Distributed Interface) implemented with only the standard library of Python 3.6. (Compatible with Python 3.6 and later.)

Follows the [INDI protocol version 1.7](http://www.clearskyinstitute.com/INDI/INDI.pdf) spec, with the following deviations:

  - supports nullable number properties (represented as the empty string or whitespace in the XML messages, as None in the Python API)
  - adds and expects the 'Z' suffix to indicate UTC in ISO timestamps (e.g. `2019-08-12T20:49:50.420459Z`) — other timezones not supported
  - does not (yet) support sexagesimal number formats in properties

**Work-in-progress, mostly undocumented, minimal test coverage. Use at your own risk!**

## Utility scripts

  * `ipyindi` - Connect to an INDI server and start an IPython REPL with the INDIClient available as `c`
  * `plotINDI` - Watch and plot a time series of changes to a (numeric) INDI property element as they happen

## Quick start

```
$ git clone https://github.com/magao-x/purepyindi.git
$ pip install -e ./purepyindi[dev,ipyindi,plotINDI]
$ ipyindi
waiting to receive properties...

known properties:

maths_x.val.value=0.0

try:

>>> c['maths_x.val.value'] = 'something'

In [1]: c['maths_x.val.value'] = 4

In [2]: print(c)

maths_x.val.value=4.0
```

## Connecting

```
from purepyindi.client import INDIClient
c = INDIClient('localhost', 7624)
c.start()
```

## Reading properties

```
print(c.devices['devicename'].properties['propertyname'].elements['elementname'].value)
# or
print(c['devicename.propertyname.elementname'])
```

## Setting properties

```
c.devices['devicename'].properties['propertyname'].elements['elementname'].value = 123.45
# or
c['devicename.propertyname.elementname'] = 123.45
```

## Watching elements

```
def my_watcher(element, did_anything_change):
    if did_anything_change:
        print(f'{element.property.device.name}.{element.property.name}.{element.name} was just updated to {element.value}')

c.devices['devicename'].properties['propertyname'].elements['elementname'].add_watcher(my_watcher)
```

## Wait for a desired state

```
targ = 50
c.wait_for_state({
    'timeSeriesSimulator.gizmo_0000.current': {
        'value': targ,
        'test': lambda current, value: abs(current - value) < tolerance,
    },
    'timeSeriesSimulator.gizmo_0000.target': {'value': targ},
    'timeSeriesSimulator.function.sin': {'value': SwitchState.ON},
})
```

The `'test'` key lets you handle approximate equality in a customizable way. The callable gets the `value` from the sibling key in that dict, and the `current` value from incoming INDI messages that update the referenced element.
