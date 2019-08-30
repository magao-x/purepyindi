'''
Pure Python INDI Client
=======================

Scientist-grade (i.e. hacky) Python library to parse INDI messages,
react to them, and issue one's own.
'''
import asyncio
import threading
import datetime
import socket
import queue
from .constants import (
    ConnectionStatus,
    INDIActions,
    INDIPropertyKind,
    PropertyPerm,
    PropertyState,
    SwitchRule,
    SwitchState,
    CHUNK_MAX_READ_SIZE,
)
from .log import debug, info, warn, error, critical
from .parser import INDIStreamParser
from .generator import mutation_to_xml_message, format_datetime_as_iso
from pprint import pprint, pformat

SYNCHRONIZATION_TIMEOUT = 1 # second

class INDIClient:
    QUEUE_CLASS = queue.Queue
    def __init__(self, host, port):
        self.host, self.port = host, port
        self.status = ConnectionStatus.STARTING
        self._outbound_queue = self.QUEUE_CLASS()
        self._inbound_queue = self.QUEUE_CLASS()
        self._parser = INDIStreamParser(self._inbound_queue)
        self.devices = {}
        self._writer = self._reader = None
        self.watchers = set()
    def add_watcher(self, watcher_callback):
        self.watchers.add(watcher_callback)
    def remove_watcher(self, watcher_callback):
        self.watchers.remove(watcher_callback)
    def _handle_outbound(self, current_socket):
        get_properties_mutation = {'action': INDIActions.GET_PROPERTIES}
        get_properties_msg = mutation_to_xml_message(get_properties_mutation)
        debug(f"sending getProperties: {get_properties_msg}")
        current_socket.sendall(get_properties_msg)
        while not self.status == ConnectionStatus.STOPPED:
            try:
                mutation = self._outbound_queue.get(timeout=SYNCHRONIZATION_TIMEOUT)
            except queue.Empty:
                continue
            debug(f"Issuing mutation:\n{pformat(mutation)}")
            outdata = mutation_to_xml_message(mutation)
            debug(f"XML for mutation:\n{outdata.decode('utf8')}")
            current_socket.sendall(outdata)
    def _handle_inbound(self, current_socket):
        while not self.status == ConnectionStatus.STOPPED:
            try:
                data = current_socket.recv(CHUNK_MAX_READ_SIZE)
            except socket.timeout:
                continue
            debug(f"Feeding to parser: {repr(data)}")
            self._parser.parse(data)
            while not self._inbound_queue.empty():
                update = self._inbound_queue.get_nowait()
                debug(f"Got update:\n{pformat(update)}")
                self.apply_update(update)
    def start(self):
        if self.status is not ConnectionStatus.CONNECTED:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self.host, self.port))
            self._socket.settimeout(SYNCHRONIZATION_TIMEOUT)
            debug("connected")
            self.status = ConnectionStatus.CONNECTED
            debug(f"Connected to {self.host}:{self.port}")
            self._writer = threading.Thread(
                target=self._handle_outbound,
                name='INDIClient-sender',
                daemon=True,
                args=(self._socket,)
            )
            self._writer.start()
            self._reader = threading.Thread(
                target=self._handle_inbound,
                name='INDIClient-receiver',
                daemon=True,
                args=(self._socket,)
            )
            self._reader.start()
    def stop(self):
        if self.status is ConnectionStatus.CONNECTED:
            self.status = ConnectionStatus.STOPPED
            self._writer.join()
            self._reader.join()
            self._writer = None
            self._reader = None
    def _new_parser(self):
        self._parser = INDIStreamParser(self._inbound_queue)
    def get_or_create_device(self, device_name):
        if device_name in self.devices:
            device = self.devices[device_name]
        else:
            device = Device(device_name, self)
            self.devices[device_name] = device
        return device
    def apply_update(self, update):
        device_name = update['device']
        if update['action'] is INDIActions.PROPERTY_DEF:
            the_device = self.get_or_create_device(device_name)
            the_device.apply_update(update)
            debug("Finished apply_update on device")
        elif update['action'] is INDIActions.PROPERTY_SET:
            if device_name in self.devices:
                self.devices[device_name].apply_update(update)
            else:
                debug(f"got an update for a property "
                      f"on a device we never saw defined: {update}")
                return False
        for watcher in self.watchers:
            watcher(update)
        return True
    def mutate(self, device, property, element, value):
        mutation = {
            'action': INDIActions.PROPERTY_NEW,
            'device': device.name,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'name': property.name,
            'elements': []
        }
        if isinstance(property, TextProperty):
            mutation['kind'] = INDIPropertyKind.TEXT
        elif isinstance(property, NumberProperty):
            mutation['kind'] = INDIPropertyKind.NUMBER
        elif isinstance(property, SwitchProperty):
            mutation['kind'] = INDIPropertyKind.SWITCH
        else:
            raise ValueError(f"Asked to mutate {property}, but don't know what kind of property it is")
        # > The Client must send all members of Number and Text
        # > vectors, or may send just the members that change
        # > for other types.
        #    - INDI Whitepaper, page 4
        if mutation['kind'] in (INDIPropertyKind.TEXT, INDIPropertyKind.NUMBER):
            for element_key in property.elements:
                mutation['elements'].append(
                    property.elements[element_key].to_dict()
                )
        else:
            mutation['elements'].append(
                element.to_dict()
            )
        debug(f"Enqueued mutation: {mutation}")
        self._outbound_queue.put_nowait(mutation)
    def to_dict(self):
        return {name: device.to_dict() for name, device in self.devices.items()}
    def __str__(self):
        str_represenation = ''
        for device_name in self.devices:
            device = self.devices[device_name]
            for property_name in device.properties:
                property = device.properties[property_name]
                for element_name in property.elements:
                    value = property.elements[element_name].value
                    str_represenation += f"{device_name}.{property_name}.{element_name}={value}\n"
        return str_represenation
    def lookup_element(self, key):
        bits = key.split('.')
        if len(bits) != 3:
            raise KeyError("Invalid key (must be of the format '<device_name>.<property_name>.<element_name>')")
        device_name, property_name, element_name = bits
        if device_name in self.devices:
            device = self.devices[device_name]
        else:
            raise KeyError(f"Unknown device {device_name}")
        if property_name in device.properties:
            property = device.properties[property_name]
        else:
            raise KeyError(f"Unknown property {property_name} for device "
                           f"{device_name} (valid properties are "
                           f"{tuple(device.properties.keys())})")
        if element_name in property.elements:
            element = property.elements[element_name]
        else:
            raise KeyError(f"Unknown element {element_name} for property "
                           f"{device_name}.{property_name}, valid elements "
                           f"are {tuple(property.elements.keys())})")
        return element
    def __contains__(self, key):
        try:
            self.lookup_element(key)
            return True
        except KeyError:
            return False
    def __getitem__(self, key):
        return self.lookup_element(key).value
    def __setitem__(self, key, value):
        element = self.lookup_element(key)
        element.value = value

class Device:
    def __init__(self, name, client_instance):
        self.client_instance = client_instance
        self.name = name
        self.properties = {}
        self.watchers = set()
    def add_watcher(self, watcher_callback):
        self.watchers.add(watcher_callback)
    def remove_watcher(self, watcher_callback):
        self.watchers.remove(watcher_callback)
    def apply_update(self, update):
        property_name = update['name']
        if update['action'] is INDIActions.PROPERTY_DEF:
            if property_name in self.properties:
                debug("WARNING: attempt to redefine existing property, ignoring")
                return
            the_prop = self.create_property(property_name, update)
            the_prop.apply_update(update)
            debug("Finished apply_update on property")
        elif update['action'] is INDIActions.PROPERTY_SET:
            if property_name in self.properties:
                self.properties[property_name].apply_update(update)
            else:
                debug(f"WARNING: got an update for a property "
                      f"we never saw defined: {update}")
        else:
            raise RuntimeError("Unknown INDIAction:", update['action'])
        for watcher in self.watchers:
            watcher(update)
    def create_property(self, property_name, update):
        kind = update['kind']
        if kind == INDIPropertyKind.NUMBER:
            prop = NumberProperty(property_name, self)
        elif kind == INDIPropertyKind.TEXT:
            prop = TextProperty(property_name, self)
        elif kind == INDIPropertyKind.SWITCH:
            prop = SwitchProperty(property_name, self)
        elif kind == INDIPropertyKind.LIGHT:
            prop = LightProperty(property_name, self)
        self.properties[property_name] = prop
        return prop
    def mutate(self, property, element, value):
        self.client_instance.mutate(self, property, element, value)
    def to_dict(self):
        return {name: prop.to_dict() for name, prop in self.properties.items()}


class Element:
    def __init__(self, name, parent_property):
        self.property = parent_property
        self.name = name
        self._value = None
        self._label = None
        self.watchers = set()
    def add_watcher(self, watcher_callback):
        self.watchers.add(watcher_callback)
    def remove_watcher(self, watcher_callback):
        self.watchers.remove(watcher_callback)
    def to_dict(self):
        return {
            'name': self.name,
            'value': self.value,
            'label': self.label,
        }
    def _update_from_server(self, element_update):
        self._value = element_update['value']
        if 'label' in element_update:
            self._label = element_update['label']
        for watcher in self.watchers:
            watcher(self)
    @property
    def label(self):
        return self._label if self._label is not None else self.name
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, new_value):
        self._value = new_value
        if self.property.perm == PropertyPerm.READ_ONLY:
            raise ValueError(
                f"Attempting to set read-only property "
                f"{self.property.name}.{self.name} "
                f"to {repr(new_value)}"
            )
        self.property.mutate(self.name, new_value)

class TextElement(Element):
    pass

class NumberElement(Element):
    format = "%e"
    min = None
    max = None
    step = None
    def to_dict(self):
        result = super().to_dict()
        result['format'] = self.format
        result['min'] = self.min
        result['max'] = self.max
        result['step'] = self.step
        return result
    def _update_from_server(self, element_update):
        super()._update_from_server(element_update)
        self.format = element_update.get('format', self.format)
        self.min = element_update.get('min', self.min)
        self.max = element_update.get('max', self.max)
        self.step = element_update.get('step', self.step)

class LightElement(Element):
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, new_value):
        raise ValueError("Clients can't change lights")

class SwitchElement(Element):
    rule = SwitchRule.ANY_OF_MANY
    def to_dict(self):
        result = super().to_dict()
        result['rule'] = self.rule.value
        return result
    def _update_from_server(self, element_update):
        super()._update_from_server(element_update)
        self.rule = element_update.get('rule', self.rule)
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, new_value):
        if new_value in SwitchState:
            super().value = new_value
        else:
            raise ValueError("Valid switch states are attributes of the SwitchState enum")

class Property:
    ELEMENT_CLASS = Element
    KIND = None
    def __init__(self, name, device):
        self.device = device
        self.name = name
        self.timestamp = None
        self.elements = {}
        self._label = None
        self._perm = None
        self.timeout = None
        self.group = None
        self._state = None
        self.message = None
        self.watchers = set()
    def add_watcher(self, watcher_callback):
        self.watchers.add(watcher_callback)
    def remove_watcher(self, watcher_callback):
        self.watchers.remove(watcher_callback)
    @property
    def state(self):
        return self._state
    @property
    def label(self):
        return self._label if self._label is not None else self.name
    @property
    def perm(self):
        return self._perm if self._perm is not None else PropertyPerm.READ_ONLY
    def to_dict(self):
        try:
            format_datetime_as_iso(self.timestamp)
        except:
            print(self.device.name, self.name, self.timestamp)
            raise
        property_dict = {
            '_timestamp': format_datetime_as_iso(self.timestamp),
            '_label': self._label,
            '_perm': self.perm.value,
            '_timeout': self.timeout,
            '_group': self.group,
            '_state': self.state.value,
            '_message': self.message,
            '_kind': self.KIND.name,
        }
        for element in self.elements:
            property_dict[element] = self.elements[element].to_dict()
        return property_dict
    def apply_update(self, update):
        self.timestamp = update.get('timestamp', self.timestamp)
        self._label = update.get('label', self._label)
        self._perm = update.get('perm', self._perm)
        self.timeout = update.get('timeout', self.timeout)
        self.group = update.get('group', self.group)
        self.timeout = update.get('timeout', self.timeout)
        self._state = update.get('state', self._state)
        for element_update in update['elements']:
            el = self.get_or_create_element(element_update['name'])
            el._update_from_server(element_update)
        for watcher in self.watchers:
            watcher(update)
    def get_or_create_element(self, element_name):
        if not element_name in self.elements:
            self.elements[element_name] = self.ELEMENT_CLASS(element_name, self)
        return self.elements[element_name]
    def mutate(self, element_name, new_value):
        self._state = PropertyState.BUSY
        self.device.mutate(self, element_name, new_value)

class TextProperty(Property):
    ELEMENT_CLASS = TextElement
    KIND = INDIPropertyKind.TEXT

class NumberProperty(Property):
    ELEMENT_CLASS = NumberElement
    KIND = INDIPropertyKind.NUMBER

class SwitchProperty(Property):
    ELEMENT_CLASS = SwitchElement
    KIND = INDIPropertyKind.SWITCH

class LightProperty(Property):
    ELEMENT_CLASS = LightElement
    KIND = INDIPropertyKind.LIGHT
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._perm = PropertyPerm.READ_ONLY
