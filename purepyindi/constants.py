from enum import Enum

__all__ = (
    'ConnectionStatus',
    'INDIActions',
    'INDIPropertyKind',
    'PropertyState',
    'PropertyPerm',
    'SwitchState',
    'SwitchRule',
    'parse_string_into_enum',
    'INDI_PROTOCOL_VERSION_STRING',
    'ISO_TIMESTAMP_FORMAT',
)

INDI_PROTOCOL_VERSION_STRING = '1.7'
ISO_TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'

class ConnectionStatus(Enum):
    STARTING = 1
    CONNECTED = 2
    RECONNECTING = 3
    STOPPED = 4

class INDIActions(Enum):
    PROPERTY_DEF = 1
    PROPERTY_SET = 2
    PROPERTY_NEW = 3
    PROPERTY_DEL = 4
    MESSAGE = 5
    GET_PROPERTIES = 6

class INDIPropertyKind(Enum):
    NUMBER = 1
    TEXT = 2
    SWITCH = 3
    LIGHT = 4

class PropertyState(Enum):
    IDLE = 'Idle'
    OK = 'Ok'
    BUSY = 'Busy'
    ALERT = 'Alert'

class PropertyPerm(Enum):
    READ_ONLY = 'ro'
    WRITE_ONLY = 'wo'
    READ_WRITE = 'rw'

class SwitchState(Enum):
    OFF = 'Off'
    ON = 'On'
    def __str__(self):
        return self.value

class SwitchRule(Enum):
    ONE_OF_MANY = 'OneOfMany'
    AT_MOST_ONE = 'AtMostOne'
    ANY_OF_MANY = 'AnyOfMany'

def parse_string_into_enum(string, enumtype):
    for entry in enumtype:
        if string == entry.value:
            return entry
    raise ValueError(f"No enum instance in {enumtype} for string {repr(string)}")
