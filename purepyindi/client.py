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
import time
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
    MAX_ELEMENT_HISTORY,
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
    def has_properties(self, properties):
        property_specs = [property_spec.split('.') for property_spec in properties]
        if not all(map(lambda x: x == 2, map(len, property_specs))):
            raise ValueError("The `properties` arg must be an iterable of strings in the format ``device_name.property_name``")
        has_all = True
        for device_name, property_name in property_specs:
            if device_name not in self.devices:
                has_all = False
            else:
                if property_name not in self.devices[device_name].properties:
                    has_all = False
        return has_all
    def wait_for_properties(self, properties, timeout=None):
        '''
        Supply an iterable of ``device_name.property_name`` strings
        and optionally a `timeout` in seconds, and this function will block
        until they are all available. Returns number of seconds it took, in case you're curious.
        '''
        ready = False
        started = time.time()
        elapsed = 0
        while not ready:
            has_all = self.has_properties(properties)
            if has_all:
                ready = True
            else:
                elapsed = time.time() - started
                debug(f'{elapsed} sec elapsed, timeout is {timeout}')
                if timeout is None or elapsed < timeout:
                    time.sleep(1)
                else:
                    raise TimeoutError(f"Timed out waiting for properties: {properties}")
        return time.time() - started
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
        '''
        Applies an update dict from the `INDIStreamParser`, returns
        whether the update actually changed the state of the world
        in INDIClient. Useful to drop updates that aren't, properly
        speaking, updating anything.
        '''
        device_name = update['device']
        if update['action'] is INDIActions.PROPERTY_DEF:
            the_device = self.get_or_create_device(device_name)
            did_anything_change = the_device.apply_update(update)
            debug("Finished apply_update on device")
        elif update['action'] in (INDIActions.PROPERTY_SET, INDIActions.PROPERTY_NEW):
            if device_name in self.devices:
                did_anything_change = self.devices[device_name].apply_update(update)
            else:
                debug(f"got an update for a property "
                      f"on a device we never saw defined: {update}")
                return False
        elif update['action'] is INDIActions.PROPERTY_DEL:
            if update['device'] not in self.devices:
                did_anything_change = False
            else:
                if 'name' in update:
                    # delete one property
                    self.devices[update['device']].apply_update(update)
                else:
                    del self.devices[update['device']]
                did_anything_change = True
        for watcher in self.watchers:
            watcher(update, did_anything_change)
        return did_anything_change
    def mutate(self, update):
        self.apply_update(update)
        self._outbound_queue.put_nowait(update)
        debug(f"Enqueued mutation: {update}")
    def to_dict(self):
        return {name: device.to_dict() for name, device in self.devices.items()}
    def to_jsonable(self):
        return {name: device.to_jsonable() for name, device in self.devices.items()}
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
    def wait_for_state(self, state_dict, wait_for_properties=False, timeout=None):
        required_properties = set()
        state_reached = state_dict.copy()
        for key, value in state_reached.items():
            state_reached[key] = False
            required_properties.add(key.rsplit('.', 1)[0])
        if wait_for_properties:
            debug(f"Waiting for properties to become available: {required_properties}")
            self.wait_for_properties(required_properties, timeout=timeout)
        def watcher_closure(the_prop):
            debug(f'in watcher_closure for {the_prop.identifier}')
            if the_prop.state is PropertyState.BUSY:
                return
            for the_elem in the_prop.elements.values():
                ident = the_elem.identifier
                if ident not in state_dict:
                    debug(f'no {ident} in {state_dict}')
                    continue
                value = state_dict[ident]['value']
                if 'test' in state_dict[ident]:
                    target_reached = state_dict[ident]['test'](the_elem.value, value)
                else:
                    target_reached = value == the_elem.value
                state_reached[ident] = target_reached
        for key, value in state_dict.items():
            element = self.lookup_element(key)
            element.property.add_watcher(watcher_closure)
            # initial evaluation to handle case where we're already at
            # requested state
            watcher_closure(element.property)
            element.value = value['value']
            debug(f"new element value: {key}={value['value']}")
            debug(f"Added watcher to element {element.identifier}")
        ready = False
        started = time.time()
        elapsed = 0
        while not ready:
            if all(state_reached.values()):
                ready = True
                break
            else:
                debug(f'Still waiting on wait_for_state: {pformat(state_reached)}')
            elapsed = time.time() - started
            debug(f'{elapsed} sec elapsed, timeout is {timeout}')
            if timeout is None or elapsed < timeout:
                time.sleep(1)
            else:
                raise TimeoutError(f"Timed out waiting for state: {state_dict}")
        for propstr in required_properties:
            devname, propname = propstr.split('.', 1)
            self.devices[devname].properties[propname].remove_watcher(watcher_closure)
        return time.time() - started



class Device:
    def __init__(self, name, client_instance):
        self.client_instance = client_instance
        self.name = name
        self.properties = {}
        self.watchers = set()
    @property
    def identifier(self):
        return f'{self.name}'
    def add_watcher(self, watcher_callback):
        self.watchers.add(watcher_callback)
    def remove_watcher(self, watcher_callback):
        self.watchers.remove(watcher_callback)
    def apply_update(self, update):
        property_name = update['property']['name']
        if update['action'] is INDIActions.PROPERTY_DEF:
            if property_name in self.properties:
                debug("WARNING: attempt to redefine existing property, ignoring")
                return False
            the_prop = self.create_property(property_name, update)
            did_anything_change = True
            the_prop.apply_update(update)
            debug("Finished apply_update on property")
        elif update['action'] in (INDIActions.PROPERTY_SET, INDIActions.PROPERTY_NEW):
            if property_name in self.properties:
                did_anything_change = self.properties[property_name].apply_update(update)
            else:
                did_anything_change = False
                debug(f"WARNING: got an update for a property "
                      f"we never saw defined: {update}")
        elif update['action'] is INDIActions.PROPERTY_DEL:
            if update['property']['name'] in self.properties:
                # delete one property
                del self.properties[update['name']]
                did_anything_change = True
        else:
            raise RuntimeError("Unknown INDIAction:", update['action'])
        for watcher in self.watchers:
            watcher(self, did_anything_change)
        return did_anything_change
    def create_property(self, property_name, update):
        kind = update['property']['kind']
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
    def mutate(self, update):
        self.client_instance.mutate(update)
    def to_dict(self):
        return {
            'name': self.name,
            'properties': {name: prop.to_dict() for name, prop in self.properties.items()},
        }
    def to_jsonable(self):
        return {
            'name': self.name,
            'properties': {name: prop.to_jsonable() for name, prop in self.properties.items()},
        }

class ElementHistory:
    def __init__(self, element, max_history=MAX_ELEMENT_HISTORY):
        self.element = element
        self.max_history = max_history
        self.times, self.values = [], []
    def add(self, timestamp, value):
        self.times.append(timestamp)
        self.values.append(value)
        if len(self.times) > self.max_history:
            self.times.pop(0)
            self.values.pop(0)
            assert len(self.times) <= self.max_history
    def to_dict(self):
        return {'times': self.times, 'values': self.values}
    def to_jsonable(self):
        the_dict = self.to_dict()
        the_dict['times'] = list(map(format_datetime_as_iso, the_dict['times']))
        if self.element.property.KIND in (INDIPropertyKind.LIGHT, INDIPropertyKind.SWITCH):
            the_dict['values'] = list(map(lambda x: x.value, the_dict['values']))
        return the_dict

class Element:
    def __init__(self, name, parent_property):
        self.property = parent_property
        self.name = name
        self._value = None
        self._label = None
        self.watchers = set()
        self.history = ElementHistory(self)
    def add_watcher(self, watcher_callback):
        self.watchers.add(watcher_callback)
    def remove_watcher(self, watcher_callback):
        self.watchers.remove(watcher_callback)
    def to_dict(self):
        return {
            'name': self.name,
            'value': self.value,
            'label': self.label,
            'history': self.history.to_dict()
        }
    def to_jsonable(self):
        the_dict = self.to_dict()
        if hasattr(the_dict['value'], 'value'):
            the_dict['value'] = the_dict['value'].value  # convert any enums into strings
        the_dict['history'] = self.history.to_jsonable()
        return the_dict
    def _update_from_server(self, element_update):
        did_anything_change = False
        if element_update['value'] != self._value:
            self._value = element_update['value']
            did_anything_change = True
        if 'label' in element_update and element_update['label'] != self._label:
            self._label = element_update['label']
            did_anything_change = True
        if did_anything_change:
            self.history.add(self.property.timestamp, self._value)
        for watcher in self.watchers:
            watcher(self, did_anything_change)
        return did_anything_change
    @property
    def label(self):
        return self._label if self._label is not None else self.name
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, new_value):
        if self.property.perm == PropertyPerm.READ_ONLY:
            raise ValueError(
                f"Attempting to set read-only property "
                f"{self.property.name}.{self.name} "
                f"to {repr(new_value)}"
            )
        self.property.mutate(self, new_value)
    @property
    def identifier(self):
        return f'{self.property.device.name}.{self.property.name}.{self.name}'

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
        did_anything_change = super()._update_from_server(element_update)
        if 'format' in element_update and element_update['format'] != self.format:
            self.format = element_update['format']
            did_anything_change = True
        if 'min' in element_update and element_update['min'] != self.min:
            self.min = element_update['min']
            did_anything_change = True
        if 'max' in element_update and element_update['max'] != self.max:
            self.max = element_update['max']
            did_anything_change = True
        if 'step' in element_update and element_update['step'] != self.step:
            self.step = element_update['step']
            did_anything_change = True
        return did_anything_change

class LightElement(Element):
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, new_value):
        raise ValueError("Clients can't change lights")

class SwitchElement(Element):
    def to_dict(self):
        result = super().to_dict()
        result['value'] = self.value.value
        return result
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, new_value):
        if new_value in SwitchState:
            return Element.value.fset(self, new_value)
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
    @property
    def identifier(self):
        return f'{self.device.name}.{self.name}'
    def to_dict(self):
        property_dict = {
            'name': self.name,
            'timestamp': self.timestamp,
            'label': self._label,
            'perm': self.perm,
            'timeout': self.timeout,
            'group': self.group,
            'state': self.state,
            'message': self.message,
            'kind': self.KIND,
            'elements': {},
        }
        for element in self.elements:
            property_dict['elements'][element] = self.elements[element].to_dict()
        return property_dict
    def to_jsonable(self):
        property_dict = {
            'name': self.name,
            'timestamp': format_datetime_as_iso(self.timestamp),
            'label': self._label,
            'perm': self.perm.value,
            'timeout': self.timeout,
            'group': self.group,
            'state': self.state.value,
            'message': self.message,
            'kind': self.KIND.value,
            'elements': {},
        }
        for element in self.elements:
            property_dict['elements'][element] = self.elements[element].to_jsonable()
        return property_dict
    def apply_update(self, update):
        did_anything_change = False
        prop = update['property']
        if 'timestamp' in prop and prop['timestamp'] != self.timestamp:
            self.timestamp = prop['timestamp']
            did_anything_change = True
        if 'label' in prop and prop['label'] != self._label:
            self._label = prop['label']
            did_anything_change = True
        if 'perm' in prop and prop['perm'] != self._perm:
            self._perm = prop['perm']
            did_anything_change = True
        if 'timeout' in prop and prop['timeout'] != self.timeout:
            self.timeout = prop['timeout']
            did_anything_change = True
        if 'group' in prop and prop['group'] != self.group:
            self.group = prop['group']
            did_anything_change = True
        if 'state' in prop and prop['state'] != self._state:
            self._state = prop['state']
            did_anything_change = True

        for element_update in prop['elements'].values():
            el = self.get_or_create_element(element_update['name'])
            did_element_change = el._update_from_server(element_update)
            assert did_element_change in (True, False), "Missing boolean return from Element._update_from_server"
            did_anything_change = did_element_change or did_anything_change
        for watcher in self.watchers:
            watcher(self, did_anything_change)
        return did_anything_change
    def get_or_create_element(self, element_name):
        if not element_name in self.elements:
            self.elements[element_name] = self.ELEMENT_CLASS(element_name, self)
        return self.elements[element_name]
    def mutate(self, element, value):
        mutation = {
            'action': INDIActions.PROPERTY_NEW,
            'device': self.device.name,
            'timestamp': format_datetime_as_iso(datetime.datetime.utcnow()),
            'property': {
                'name': self.name,
                'kind': self.KIND,
                'elements': {},
                'state': PropertyState.BUSY
            }
        }
        # > The Client must send all members of Number and Text
        # > vectors, or may send just the members that change
        # > for other types.
        #    - INDI Whitepaper, page 4
        if mutation['property']['kind'] in (INDIPropertyKind.TEXT, INDIPropertyKind.NUMBER):
            for element_key in self.elements:
                mutation['property']['elements'][element_key] = self.elements[element_key].to_dict()
        else:
            mutation['property']['elements'][element.name] = element.to_dict()
        # Actually encode the new value
        mutation['property']['elements'][element.name]['value'] = value
        self.device.mutate(mutation)

class TextProperty(Property):
    ELEMENT_CLASS = TextElement
    KIND = INDIPropertyKind.TEXT

class NumberProperty(Property):
    ELEMENT_CLASS = NumberElement
    KIND = INDIPropertyKind.NUMBER

class SwitchProperty(Property):
    ELEMENT_CLASS = SwitchElement
    KIND = INDIPropertyKind.SWITCH
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rule = None
    def apply_update(self, update):
        did_anything_change = False
        prop = update['property']
        if 'rule' in prop and prop['rule'] != self.rule:
            self.rule = prop['rule']
            did_anything_change = True
        did_super_change = super().apply_update(update)
        return did_super_change or did_anything_change
    def to_dict(self):
        the_dict = super().to_dict()
        the_dict['rule'] = self.rule.value
        return the_dict

class LightProperty(Property):
    ELEMENT_CLASS = LightElement
    KIND = INDIPropertyKind.LIGHT
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._perm = PropertyPerm.READ_ONLY
