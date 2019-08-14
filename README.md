# purepyindi

An INDI client implemented with only the standard library

**Work-in-progress, undocumented, use at your own risk.**

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
