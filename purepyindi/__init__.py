from .client import INDIClient
from .parser import INDIStreamParser
from .constants import (
    ConnectionStatus,
    INDIActions,
    INDIPropertyKind,
    PropertyState,
    PropertyPerm,
    SwitchState,
    SwitchRule,
    parse_string_into_enum,
    INDI_PROTOCOL_VERSION_STRING,
    ISO_TIMESTAMP_FORMAT,
)
from os.path import dirname, join
with open(join(dirname(__file__), 'VERSION')) as f:
    __version__ = f.read().strip()

__all__ = (
    'INDIClient',
    'INDIStreamParser',
    'ConnectionStatus',
    'PropertyState',
    'PropertyPerm',
    'SwitchState',
    'SwitchRule',
    'INDI_PROTOCOL_VERSION_STRING',
)
