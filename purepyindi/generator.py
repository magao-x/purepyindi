import xml.etree.ElementTree as ET
import datetime
from .constants import (
    INDIPropertyKind,
    INDIActions,
    ISO_TIMESTAMP_FORMAT,
    INDI_PROTOCOL_VERSION_STRING,
)

KINDS_TO_NEW_TAG_NAMES = {
    INDIPropertyKind.NUMBER: ('newNumberVector', 'oneNumber'),
    INDIPropertyKind.TEXT: ('newTextVector', 'oneText'),
    INDIPropertyKind.SWITCH: ('newSwitchVector', 'oneSwitch'),
}

def format_datetime_as_iso(dt):
    return dt.astimezone(datetime.timezone.utc).strftime(ISO_TIMESTAMP_FORMAT)

def construct_property_new(mutation, timestamp):
    root_tag, sub_tag = KINDS_TO_NEW_TAG_NAMES[mutation['property']['kind']]
    xml_doc = ET.Element(root_tag, attrib={
        'device': mutation['device'],
        'name': mutation['property']['name'],
        'timestamp': format_datetime_as_iso(timestamp),
    })
    for element in mutation['property']['elements'].values():
        sub = ET.SubElement(xml_doc, sub_tag, attrib={'name': element['name']})
        if mutation['property']['kind'] == INDIPropertyKind.NUMBER:
            sub.text = (
                element['format'] % (element['value'],)
                if element['value'] is not None
                else ''
            )
        elif mutation['property']['kind'] == INDIPropertyKind.SWITCH:
            sub.text = element['value'].value
        else:
            sub.text = element['value']
    return xml_doc

def construct_get_properties(mutation):
    attribs = {
        'version': INDI_PROTOCOL_VERSION_STRING,
    }
    if 'device' in mutation:
        attribs['device'] = mutation['device']
        if 'name' in mutation:
            attribs['name'] = mutation['name']
    return ET.Element('getProperties', attrib=attribs)

def mutation_to_xml_message(mutation, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.utcnow()
    if mutation['action'] is INDIActions.PROPERTY_NEW:
        xml_doc = construct_property_new(mutation, timestamp)
    elif mutation['action'] is INDIActions.GET_PROPERTIES:
        xml_doc = construct_get_properties(mutation)
    xml_message = ET.tostring(xml_doc, encoding='unicode')
    return xml_message.encode('utf8') + b'\n'
