from enum import Enum
from functools import wraps
from xml.parsers import expat
import datetime
from .constants import (
    ISO_TIMESTAMP_FORMAT,
    INDIPropertyKind,
    INDIActions,
    PropertyPerm,
    PropertyState,
    SwitchRule,
    SwitchState,
    parse_string_into_enum,
)
from .log import debug, info, warn, error, critical

def parse_iso_to_datetime(timestamp):
    dt = datetime.datetime.strptime(timestamp, ISO_TIMESTAMP_FORMAT)
    dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt

class INDIStreamParser:
    PROPERTY_DEF_TAGS = {
        'defNumberVector': INDIPropertyKind.NUMBER,
        'defTextVector': INDIPropertyKind.TEXT,
        'defSwitchVector': INDIPropertyKind.SWITCH,
        'defLightVector': INDIPropertyKind.LIGHT,
    }
    ELEMENT_DEF_TAGS = {
        'defNumber',
        'defText',
        'defSwitch',
        'defLight',
    }
    OPTIONAL_PROPERTY_DEF_ATTRS = {
        'label',
        'group',
        'timeout',
        'timestamp',
        'message',
    }
    PROPERTY_SET_TAGS = {
        'setNumberVector': INDIPropertyKind.NUMBER,
        'setTextVector': INDIPropertyKind.TEXT,
        'setSwitchVector': INDIPropertyKind.SWITCH,
        'setLightVector': INDIPropertyKind.LIGHT,
    }
    OPTIONAL_PROPERTY_SET_ATTRS = {
        'state',
        'timeout',
        'timestamp',
        'message',
    }
    ELEMENT_SET_TAGS = {
        'oneNumber',
        'oneText',
        'oneSwitch',
        'oneLight',
    }

    def __init__(self, update_queue):
        self.update_queue = update_queue
        # self.open_elements = []
        self.current_indi_element = None
        self.pending_update = None
        self.accumulated_chardata = ''
        self.accumulated_elements = []
        self.parser = self._new_parser()

    def _new_parser(self):
        parser = expat.ParserCreate()
        parser.StartElementHandler = self.start_element_handler
        parser.EndElementHandler = self.end_element_handler
        parser.CharacterDataHandler = self.character_data_handler
        parser.Parse('<indi>')
        return parser

    def parse(self, data):
        try:
            self.parser.Parse(data)
        except expat.ExpatError as e:
            self.parser = self._new_parser()
            self.accumulated_chardata = ''
            self.pending_update = None
            self.current_indi_element = None
            warn(f"reset parser state after encountering bad input: {e}")

    # @_reset_on_bad_input
    def start_element_handler(self, tag_name, tag_attributes):
        if self.accumulated_chardata.strip():
            debug(f'character data {repr(self.accumulated_chardata)} cannot be sibling of element, discarding')

        if tag_name in self.PROPERTY_DEF_TAGS:
            if self.pending_update is not None:
                debug(f'property definition happening while we '
                      f'thought something else was happening. '
                      f'Discarded pending update was: '
                      f'{self.pending_update}')
            self.pending_update = {
                'action': INDIActions.PROPERTY_DEF,
                'kind': self.PROPERTY_DEF_TAGS[tag_name],
                'device': tag_attributes['device'],
                'name': tag_attributes['name'],
                'elements': [],
                'perm': parse_string_into_enum(tag_attributes['perm'], PropertyPerm),
                'state': parse_string_into_enum(tag_attributes['state'], PropertyState)
            }
            if self.pending_update['kind'] == INDIPropertyKind.SWITCH:
                self.pending_update['rule'] = parse_string_into_enum(tag_attributes['rule'], SwitchRule)
            for optional_attr in self.OPTIONAL_PROPERTY_DEF_ATTRS:
                if optional_attr in tag_attributes:
                    if optional_attr == 'timestamp':
                        self.pending_update[optional_attr] = tag_attributes[optional_attr]
                    else:
                        self.pending_update[optional_attr] = tag_attributes[optional_attr]
        elif tag_name in self.PROPERTY_SET_TAGS:
            if self.pending_update is not None:
                debug(f'property setting happening while we thought '
                      f'something else was happening. '
                      f'Discarded pending update was: '
                      f'{self.pending_update}')
            self.pending_update = {
                'action': INDIActions.PROPERTY_SET,
                'kind': self.PROPERTY_SET_TAGS[tag_name],
                'device': tag_attributes['device'],
                'name': tag_attributes['name'],
                'elements': [],
            }
            for optional_attr in self.OPTIONAL_PROPERTY_SET_ATTRS:
                if optional_attr in tag_attributes:
                    if optional_attr == 'state':
                        self.pending_update[optional_attr] = parse_string_into_enum(tag_attributes[optional_attr], PropertyState)
                    else:
                        self.pending_update[optional_attr] = tag_attributes[optional_attr]
        elif tag_name in self.ELEMENT_DEF_TAGS or tag_name in self.ELEMENT_SET_TAGS:
            if self.pending_update is None:
                debug(f'element definition/setting happening outside property definition/setting')
                self.current_indi_element = None
                return
            self.current_indi_element = {
                'name': tag_attributes['name']
            }
            if tag_name == 'defNumber':
                self.current_indi_element.update({
                    'format': tag_attributes['format'],
                    'min': float(tag_attributes['min']),
                    'max': float(tag_attributes['max']),
                    'step': float(tag_attributes['step']),
                })
            if 'label' in tag_attributes:
                self.current_indi_element['label'] = tag_attributes['label']

    # @_reset_on_bad_input
    def end_element_handler(self, tag_name):
        contents = self.accumulated_chardata.strip()
        self.accumulated_chardata = ''
        if tag_name in self.ELEMENT_DEF_TAGS or tag_name in self.ELEMENT_SET_TAGS:
            element = self.current_indi_element
            if element is None:
                return
            if not contents.strip():
                # Notable spec deviation: Unset elements are not
                # provided for in INDI, but have their uses.
                # They are represented by `None` in the Python API.
                element['value'] = None
            elif self.pending_update['kind'] == INDIPropertyKind.NUMBER:
                try:
                    parsed_number = float(contents)
                except ValueError:
                    warn(f"Coudn't parse {contents} as a number for {self.pending_update['device']}.{self.pending_update['name']}.{element['name']}")
                    parsed_number = float('nan')
                element['value'] = parsed_number
            elif self.pending_update['kind'] == INDIPropertyKind.SWITCH:
                element['value'] = parse_string_into_enum(contents, SwitchState)
            elif self.pending_update['kind'] == INDIPropertyKind.LIGHT:
                element['value'] = parse_string_into_enum(contents, PropertyState)
            else:
                element['value'] = contents
            self.pending_update['elements'].append(element)
            self.current_indi_element = None
        elif tag_name in self.PROPERTY_DEF_TAGS or tag_name in self.PROPERTY_SET_TAGS:
            self.update_queue.put_nowait(self.pending_update)
            self.pending_update = None

    def character_data_handler(self, data):
        self.accumulated_chardata += data
