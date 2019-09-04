import asyncio
from .parser import INDIStreamParser
from .constants import *
from .test_fixtures import (
    DEF_NUMBER_PROP,
    DEF_NUMBER_UPDATE,
    SET_NUMBER_PROP,
    SET_NUMBER_UPDATE,
    DEL_PROPERTY_MESSAGE,
    DEL_PROPERTY_UPDATE,
)
from pprint import pprint
from io import BytesIO


def test_number_update():
    input_buffer = BytesIO(DEF_NUMBER_PROP + SET_NUMBER_PROP)
    q = asyncio.Queue()
    parser = INDIStreamParser(q)
    data = input_buffer.read(len(DEF_NUMBER_PROP))
    parser.parse(data)
    def_update_payload = q.get_nowait()
    assert def_update_payload == DEF_NUMBER_UPDATE
    data = input_buffer.read(len(SET_NUMBER_PROP))
    parser.parse(data)
    set_update_payload = q.get_nowait()
    assert set_update_payload == SET_NUMBER_UPDATE

def test_delete_device():
    import logging
    logging.basicConfig(level='DEBUG')
    input_buffer = BytesIO(DEL_PROPERTY_MESSAGE)
    q = asyncio.Queue()
    parser = INDIStreamParser(q)
    data = input_buffer.read(len(DEL_PROPERTY_MESSAGE))
    parser.parse(data)
    del_property_parsed = q.get_nowait()
    assert del_property_parsed == DEL_PROPERTY_UPDATE
