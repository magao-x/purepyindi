import asyncio
from .test_fixtures import (
    NEW_NUMBER_MUTATION,
    NEW_NUMBER_MESSAGE,
    NEW_NUMBER_TIMESTAMP,
)
from .generator import mutation_to_xml_message
from pprint import pprint
from io import BytesIO

def test_generator():
    message = mutation_to_xml_message(NEW_NUMBER_MUTATION, timestamp=NEW_NUMBER_TIMESTAMP)
    assert message == NEW_NUMBER_MESSAGE
