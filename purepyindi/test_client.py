import asyncio
from .constants import *
from pprint import pprint
from .client import INDIClient

from .test_fixtures import (
    DEF_NUMBER_UPDATE,
    SET_NUMBER_UPDATE,
)
from pprint import pprint

def test_number_update():
    client = INDIClient(None, None)
    assert 'test' not in client.devices
    client.apply_update(DEF_NUMBER_UPDATE)
    assert 'test' in client.devices
    pprint(client.devices['test'].to_dict())
    assert client.devices['test'].properties['prop'].elements['value'].value == 0

def test_start_stop_start_stop():
    client = INDIClient('localhost', 7624)
    client.start()
    client.stop()
    client.start()
    client.stop()
