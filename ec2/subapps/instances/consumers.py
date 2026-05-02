import asyncio
import json
import threading

from channels.generic.websocket import AsyncWebsocketConsumer

import docker_ops
from docker_ops.exceptions import ContainerOpException

from .models import Instance


class TerminalConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        pk = self.scope["url_route"]["kwargs"]["pk"]

        try:
            self.instance = await Instance.objects.aget(pk=pk, owner=user)
        except Instance.DoesNotExist:
            await self.close(code=4004)
            return

        if not self.instance.docker_container_id:
            await self.close(code=4003)
            return

        loop = asyncio.get_running_loop()
        try:
            self._exec_id, self._sock = await loop.run_in_executor(
                None,
                lambda: docker_ops.containers.exec_interactive(
                    self.instance.docker_container_id
                ),
            )
        except ContainerOpException:
            await self.close(code=4002)
            return

        await self.accept()

        self._loop = asyncio.get_running_loop()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._closed = False

        self._reader_thread = threading.Thread(
            target=self._docker_reader, daemon=True
        )
        self._reader_thread.start()

        self._sender_task = asyncio.create_task(self._sender_loop())

    def _docker_reader(self):
        """Blocking thread: drains the Docker exec socket into the async queue.

        Uses recv() in blocking mode (not select+recv) — docker-py 7.x returns
        a SocketIO whose underlying socket can be marked non-blocking by the
        transport layer, which made select.select report 'not ready' even when
        the kernel had data buffered. disconnect() closes the socket to wake
        recv with an empty read.
        """
        raw_sock = self._sock._sock
        try:
            raw_sock.setblocking(True)
        except OSError:
            pass
        try:
            while not self._closed:
                try:
                    data = raw_sock.recv(4096)
                except OSError:
                    break
                if not data:
                    break
                asyncio.run_coroutine_threadsafe(self._queue.put(data), self._loop)
        finally:
            asyncio.run_coroutine_threadsafe(self._queue.put(None), self._loop)

    async def _sender_loop(self):
        """Async loop: drains queue and forwards data to the WebSocket."""
        try:
            while True:
                chunk = await self._queue.get()
                if chunk is None:
                    await self.close()
                    break
                await self.send(bytes_data=chunk)
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        # Preferred: bytes_data carries raw input, text_data carries JSON
        # control messages. We also tolerate raw input over text_data so a
        # cached client still works. The old code parsed every text frame as
        # JSON and crashed on non-dicts (e.g. json.loads("1") == 1, then
        # 1.get(...) raised AttributeError) — that swallowed every digit.
        if self._closed or not hasattr(self, "_sock"):
            return

        loop = asyncio.get_running_loop()

        if bytes_data:
            await loop.run_in_executor(None, self._sock._sock.send, bytes_data)
            return

        if not text_data:
            return

        try:
            msg = json.loads(text_data)
        except json.JSONDecodeError:
            msg = None

        if isinstance(msg, dict) and msg.get("type") == "resize":
            try:
                rows = int(msg["rows"])
                cols = int(msg["cols"])
            except (KeyError, TypeError, ValueError):
                return
            await loop.run_in_executor(
                None,
                lambda: docker_ops.containers.resize_exec(
                    self._exec_id, rows=rows, cols=cols
                ),
            )
            return

        # Anything else on a text frame: treat as raw input.
        await loop.run_in_executor(
            None, self._sock._sock.send, text_data.encode()
        )

    async def disconnect(self, close_code):
        self._closed = True
        if hasattr(self, "_sender_task"):
            self._sender_task.cancel()
        if hasattr(self, "_sock"):
            try:
                self._sock.close()
            except Exception:
                pass
