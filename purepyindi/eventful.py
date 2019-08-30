import asyncio
from pprint import pformat
from .client import INDIClient
from .constants import *
from .generator import mutation_to_xml_message
from .log import debug, info, warn

RECONNECTION_DELAY = 2

class AsyncINDIClient(INDIClient):
    QUEUE_CLASS = asyncio.Queue
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.async_watchers = set()
    def add_async_watcher(self, watcher_callback):
        self.async_watchers.add(watcher_callback)
    def remove_async_watcher(self, watcher_callback):
        self.async_watchers.remove(watcher_callback)
    def start(self):
        raise NotImplementedError("To start, schedule an async task for AsyncINDIClient.run")
    async def run(self, reconnect_automatically=False):
        connect = True
        while connect:
            try:
                reader_handle, writer_handle = await asyncio.open_connection(
                    self.host,
                    self.port
                )
                addr = writer_handle.get_extra_info("peername")
                info(f"Connected to {addr!r}")
                await self._outbound_queue.put({'action': INDIActions.GET_PROPERTIES})
                self._reader = asyncio.ensure_future(self._handle_inbound(reader_handle))
                self._writer = asyncio.ensure_future(self._handle_outbound(writer_handle))
                await asyncio.gather(
                    self._reader, self._writer
                )
            except ConnectionError as e:
                warn(f"Failed to connect: {repr(e)}")
                if reconnect_automatically:
                    warn(f"Retrying in {RECONNECTION_DELAY} seconds")
            except Exception as e:
                warn(f"Swallowed exception: {type(e)}")
                self.stop()
            connect = reconnect_automatically
            await asyncio.sleep(RECONNECTION_DELAY)
    async def stop(self):
        self.status = ConnectionStatus.STOPPED
        if self._reader is not None:
            self._reader.cancel()
        if self._writer is not None:
            self._writer.cancel()
    async def _handle_inbound(self, reader_handle):
        while not self.status == ConnectionStatus.STOPPED:
            data = await reader_handle.read(CHUNK_MAX_READ_SIZE)
            debug(f"Feeding to parser: {repr(data)}")
            self._parser.parse(data)
            while not self._inbound_queue.empty():
                update = await self._inbound_queue.get()
                debug(f"Got update:\n{pformat(update)}")
                did_apply = self.apply_update(update)
                if not did_apply:
                    continue
                for watcher in self.async_watchers:
                    await watcher(update)
    async def _handle_outbound(self, writer_handle):
        while not self.status == ConnectionStatus.STOPPED:
            try:
                mutation = await self._outbound_queue.get()
                outdata = mutation_to_xml_message(mutation)
                writer_handle.write(outdata)
                await writer_handle.drain()
            except asyncio.CancelledError:
                writer_handle.close()
                await writer_handle.wait_closed()
                raise
