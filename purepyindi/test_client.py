import pytest
import asyncio
from unittest import mock
from .constants import *
from pprint import pprint
from .client import INDIClient

from .test_fixtures import (
    DEF_NUMBER_UPDATE,
    SET_NUMBER_UPDATE,
    DEL_PROPERTY_UPDATE,
)
from pprint import pprint

def test_number_update():
    client = INDIClient(None, None)
    assert 'test' not in client.devices
    client.apply_update(DEF_NUMBER_UPDATE)
    assert 'test' in client.devices
    pprint(client.devices['test'].to_dict())
    assert client.devices['test'].properties['prop'].elements['value'].value == 0

def test_delete_device():
    client = INDIClient(None, None)
    client.apply_update(DEF_NUMBER_UPDATE)
    assert 'test' in client.devices
    client.apply_update(DEL_PROPERTY_UPDATE)
    assert 'test' not in client.devices

def test_wait_for_properties_timeout():
    client = INDIClient(None, None)
    with pytest.raises(TimeoutError):
        client.wait_for_properties(['test.prop'], timeout=0)
    client.apply_update(DEF_NUMBER_UPDATE)
    client.wait_for_properties(['test.prop'], timeout=0)

def test_wait_for_properties_argformat():
    client = INDIClient(None, None)
    with pytest.raises(ValueError):
        client.wait_for_properties(['test.prop.element'], timeout=0)

def test_did_anything_change():
    client = INDIClient(None, None)
    did_anything_change = client.apply_update(DEF_NUMBER_UPDATE)
    assert did_anything_change == True
    did_anything_change = client.apply_update(DEF_NUMBER_UPDATE)
    assert did_anything_change == True  # n.b. recreating a property counts as changing!
    did_anything_change = client.apply_update(SET_NUMBER_UPDATE)
    assert did_anything_change == True
    did_anything_change = client.apply_update(SET_NUMBER_UPDATE)
    assert did_anything_change == False
    did_anything_change = client.apply_update(DEL_PROPERTY_UPDATE)
    assert did_anything_change == True
    did_anything_change = client.apply_update(DEL_PROPERTY_UPDATE)
    assert did_anything_change == False

def test_start_stop_start_stop():
    with mock.patch('socket.socket') as mock_socket:
        mock_socket.connect.return_value = True
        mock_socket.sendall.return_value = None
        mock_socket.recv.return_value = ''
        client = INDIClient('localhost', 7624)
        client.start()
        client.stop()
        client.start()
        client.stop()

