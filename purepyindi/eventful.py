import asyncio
import time
from pprint import pformat
from .client import INDIClient
from .constants import *
from .generator import mutation_to_xml_message
import logging

RECONNECTION_DELAY = 2
SOCKET_READ_TIMEOUT = 60

log = logging.getLogger(__name__)

class AsyncINDIClient(INDIClient):
    QUEUE_CLASS = asyncio.Queue
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.async_watchers = set()
    async def wait_for_properties(self, properties, timeout=None):
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
                if timeout is None or elapsed < timeout:
                    await asyncio.sleep(1)
                else:
                    raise TimeoutError(f"Timed out waiting for properties: {properties}")
        return time.time() - started
    async def wait_for_state(self, state_dict, wait_for_properties=False, timeout=None):
        raise NotImplementedError("Still needs async implementation!")
    def add_async_watcher(self, watcher_callback):
        self.async_watchers.add(watcher_callback)
    def remove_async_watcher(self, watcher_callback):
        self.async_watchers.remove(watcher_callback)
    def start(self):
        raise NotImplementedError("To start, schedule an async task for AsyncINDIClient.run")
    async def run(self, reconnect_automatically=False):
        while self.status is not ConnectionStatus.STOPPED:
            try:
                reader_handle, writer_handle = await asyncio.open_connection(
                    self.host,
                    self.port
                )
                addr = writer_handle.get_extra_info("peername")
                log.info(f"Connected to {addr!r}")
                self.status = ConnectionStatus.CONNECTED
                self.get_properties()
                self._reader = asyncio.ensure_future(self._handle_inbound(reader_handle))
                self._writer = asyncio.ensure_future(self._handle_outbound(writer_handle))
                try:
                    await asyncio.gather(
                        self._reader, self._writer
                    )
                except asyncio.CancelledError:
                    continue
            except ConnectionError as e:
                log.warn(f"Failed to connect: {repr(e)}")
                if reconnect_automatically:
                    log.warn(f"Retrying in {RECONNECTION_DELAY} seconds")
            except Exception as e:
                log.warn(f"Swallowed exception: {type(e)}, {e}")
                raise
            finally:
                self._cancel_tasks()
            if reconnect_automatically:
                self.status = ConnectionStatus.RECONNECTING
                await asyncio.sleep(RECONNECTION_DELAY)
            else:
                raise ConnectionError(f"Got disconnected from {self.host}:{self.port}, not attempting reconnection")
    def _cancel_tasks(self):
        if self._reader is not None:
            self._reader.cancel()
        if self._writer is not None:
            self._writer.cancel()
    async def stop(self):
        self.status = ConnectionStatus.STOPPED
        self._cancel_tasks()
    async def _handle_inbound(self, reader_handle):
        while self.status == ConnectionStatus.CONNECTED:
            try:
                data = await asyncio.wait_for(reader_handle.read(CHUNK_MAX_READ_SIZE), SOCKET_READ_TIMEOUT)
            except asyncio.TimeoutError:
                log.debug(f"No data for {SOCKET_READ_TIMEOUT} sec")
                continue
            if data == b'':
                log.debug("Got EOF from server")
                raise ConnectionError("Got EOF from server")
            log.debug(f"Feeding to parser: {repr(data)}")
            self._parser.parse(data)
            while not self._inbound_queue.empty():
                update = await self._inbound_queue.get()
                log.debug(f"Got update:\n{pformat(update)}")
                did_anything_change = self.apply_update(update)
                for watcher in self.async_watchers:
                    await watcher(update, did_anything_change)
    async def _handle_outbound(self, writer_handle):
        while self.status == ConnectionStatus.CONNECTED:
            try:
                mutation = await self._outbound_queue.get()
                outdata = mutation_to_xml_message(mutation)
                writer_handle.write(outdata)
                await writer_handle.drain()
            except asyncio.CancelledError:
                writer_handle.close()
                await writer_handle.wait_closed()
                raise
