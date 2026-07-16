"""Multi-user chat server.

Listens on a TCP port, accepts any number of chat clients, and relays
every message a *writer* sends to every connected *reader*.
"""

import argparse
import asyncio
import datetime
import random

import aiohttp

import common
from const import (
    DEFAULT_HOST, BUFFER_SIZE, TYPE_IMAGE, TYPE_MSG, TYPE_HELLO,
    MODE_READER, TIME_FORMAT, IMAGE_PROCESSING_DELAY, CACHE_MISS_MESSAGE,
    CACHE_HIT_MESSAGE, SERVER_STOP_MESSAGE, SERVER_SHUTDOWN_MESSAGE,
    DEFAULT_USERNAME, EMPTY_STRING, TYPE_MATRIX, FAST_API_URL,
    TYPE_PREMONITIONS, MODE_DUPLEX, DEFAULT_LOG_FILE_PATH, MODE_WRITER
)
from utils import initiate_logger, tokens_over_used, check_how_many_clients_there_is, PortValidator

logger = initiate_logger()


class ClientState:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info("peername")
        self.buffer = common.LineBuffer()
        self.username = None
        self.mode = None


class AsyncChatServer(object, metaclass=PortValidator):
    HOST = DEFAULT_HOST
    PORT = 7777

    def __init__(self, port, log_path=DEFAULT_LOG_FILE_PATH):
        self.port = port or self.PORT
        self.log_path = log_path
        self.clients = {}  # socket writer -> ClientState
        self._logger = initiate_logger(self.log_path)
        self.image_db = {}

    # -- setup / teardown -------------------------------------------------

    def close(self):
        """Close all client sockets, the listener, and the log handlers."""
        for state in list(self.clients.values()):
            self._drop_sync(state.writer)
        for handler in list(self._logger.handlers):
            handler.flush()
            handler.close()
            self._logger.removeHandler(handler)

    def _drop_sync(self, writer):
        """Non-async helper to cleanly drop clients during close() teardown."""
        self.clients.pop(writer, None)
        try:
            writer.close()
        except Exception:
            pass

    # -- main loop --------------------------------------------------------

    async def run(self):
        server = await asyncio.start_server(
            self.handle_client,
            self.HOST,
            self.port
        )
        self._logger.info(
            "Chat server listening on port {} - logging to {}".format(self.port,
            self.log_path)
        )

        self._logger.debug(SERVER_STOP_MESSAGE)
        async with server:
            await server.serve_forever()

    async def handle_client(self, reader, writer):
        state = ClientState(reader, writer)
        self.clients[writer] = state

        try:
            while True:
                data = await reader.read(BUFFER_SIZE)
                if not data:
                    break

                for message in state.buffer.feed(data):
                    await self._dispatch(state, message)
        except ConnectionError:
            pass  # Client disconnected abruptly
        finally:
            await self._drop(writer)

    async def _dispatch(self, state, message):
        if check_how_many_clients_there_is(self.clients):
            return

        msg_type = message.get("type")

        if msg_type == TYPE_HELLO:
            state.mode = message.get("mode")
            state.username = message.get("username") or DEFAULT_USERNAME
            self._logger.info("Client %s connected in %s mode from %s", state.username, state.mode, state.addr[0])

        elif msg_type == TYPE_MSG:
            await self._handle_chat(state, message.get("text", EMPTY_STRING))

        elif msg_type == TYPE_IMAGE:
            full_path = message.get("path")
            self._logger.info("Client sent %s", msg_type)

            # FAST IN-MEMORY CHECK (O(1) Speed Lookup)
            if full_path in self.image_db:
                self._logger.info(CACHE_HIT_MESSAGE)

                cached_payload = self.image_db[full_path]
                tokens_over_used(self.log_path)

                # Send straight to readers/duplex immediately
                frame = common.encode(cached_payload)
                for other in self.clients.values():
                    if other.mode in (MODE_READER, MODE_DUPLEX):
                        other.writer.write(frame)
                        await other.writer.drain()
            else:
                # Cache MISS: First time seeing this image, process it normally
                self._logger.info(CACHE_MISS_MESSAGE)
                await self._handle_image_path(state, full_path)

        elif msg_type == TYPE_MATRIX:
            await self._handle_matrix(state, message.get("content", EMPTY_STRING))

        elif msg_type == TYPE_PREMONITIONS:
            await self._handle_premonitions(state, message.get("premonitions", EMPTY_STRING))

    async def _handle_chat(self, state, text):
        """Log an incoming chat line and fan it out to all readers."""
        username = state.username or DEFAULT_USERNAME
        timestamp = datetime.datetime.now().strftime(TIME_FORMAT)

        self._logger.info("%s, %s, %s", username, timestamp, text)

        # Broadcast the formatted payload back out
        chat_payload = common.make_chat(username, timestamp, text)
        await self.broadcast(chat_payload)

    async def _handle_image_path(self, state, path):
        """Log an incoming image path and fan it out to all readers."""
        username = state.username or DEFAULT_USERNAME
        timestamp = datetime.datetime.now().strftime(TIME_FORMAT)

        await asyncio.sleep(IMAGE_PROCESSING_DELAY)
        self._logger.info("%s shared an image: %s at %s", username, path, timestamp)

        image_broadcast_payload = common.make_image(path, username)
        image_broadcast_payload["timestamp"] = timestamp

        self.image_db[path] = image_broadcast_payload
        await self.broadcast(image_broadcast_payload)

    async def _handle_matrix(self, state, payload):
        async with aiohttp.ClientSession() as session:
            async with session.post(FAST_API_URL, json=payload) as response:
                result = await response.json()

        username = state.username or DEFAULT_USERNAME
        matrix_payload = common.make_matrix(result, username)
        await self.broadcast(matrix_payload)

    async def _handle_premonitions(self, state, payload):
        """Processes two words and broadcasts premonitions results back."""
        logger.info("Premonitions payload: %s", payload)
        client_output = payload.split()
        if len(client_output) < 2:
            logger.warning("Premonition requires at least 2 words.")
            return

        word_to_check_one = client_output[0]
        word_to_check_two = client_output[1]

        # Fix range to include option 3 (1, 2, or 3)
        random_number = random.randint(1, 3)
        result_for_client = False

        if random_number == 1:
            clean1 = sorted(word_to_check_one.replace(" ", EMPTY_STRING).lower())
            clean2 = sorted(word_to_check_two.replace(" ", EMPTY_STRING).lower())
            result_for_client = (clean1 == clean2)
        elif random_number == 2:
            clean1 = word_to_check_one.replace(" ", EMPTY_STRING).lower()
            clean2 = word_to_check_two.replace(" ", EMPTY_STRING).lower()
            result_for_client = (clean1 == clean2)
        elif random_number == 3:
            # Concrete implementation for Option 3: Substring match check
            clean1 = word_to_check_one.replace(" ", EMPTY_STRING).lower()
            clean2 = word_to_check_two.replace(" ", EMPTY_STRING).lower()
            result_for_client = (clean1 in clean2 or clean2 in clean1)

        # Broadcast the structured payload
        premonition_payload = common.make_premonitions(result_for_client, state.username or DEFAULT_USERNAME)
        await self.broadcast(premonition_payload)

    async def broadcast(self, payload):
        """Encodes the python dict payload ONCE and broadcasts to readers."""
        encoded_frame = common.encode(payload)
        logger.info("Broadcasting payload to %d clients", len(self.clients))

        for client in list(self.clients.values()):
            if client.mode in (MODE_READER, MODE_DUPLEX):
                try:
                    client.writer.write(encoded_frame)
                    await client.writer.drain()
                except ConnectionError:
                    # Under-the-hood socket cleaning handled on loop failure
                    pass

    async def _drop(self, writer):
        """Remove and close a client socket cleanly."""
        state = self.clients.pop(writer, None)
        if state:
            if state.username:
                self._logger.info("Client disconnected: %s", state.username)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


def parse_args():
    parser = argparse.ArgumentParser(description="Multi-user chat server.")
    parser.add_argument("-p", "--port", type=int, default=7777,
                        help="Port to listen on (default: 7777)")
    parser.add_argument("-l", "--log", default="log.csv",
                        help="Log file (default: log.csv)")
    return parser.parse_args()


def main():
    args = parse_args()
    server = AsyncChatServer(args.port, args.log)

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print(SERVER_SHUTDOWN_MESSAGE)
    finally:
        server.close()
        print("Log file closed. Bye.")


if __name__ == "__main__":
    main()