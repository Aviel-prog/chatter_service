"""Multi-user chat server.

Listens on a TCP port, accepts any number of chat clients, and relays
every message a *writer* sends to every connected *reader*.  All chat
messages are appended to a CSV-formatted log (username, date+time,
message) using the standard ``logging`` module.

Concurrency is handled with a single ``select.select`` loop over
non-blocking sockets -- no threads.  The server runs until the operator
presses Ctrl-C, at which point it flushes and closes the log handlers
so no chat data is lost.

Usage::

    server.py [-p PORT] [-l LOG]

    -p PORT   Port to listen on (default: 7777)
    -l LOG    Log file (default: log.csv)
"""

import argparse
import asyncio
import datetime
import random
import socket
import aiohttp
import common
from const import DEFAULT_HOST, BUFFER_SIZE, TYPE_IMAGE, TYPE_MSG, TYPE_HELLO, MODE_READER, TIME_FORMAT, \
    IMAGE_PROCESSING_DELAY, CACHE_MISS_MESSAGE, CACHE_HIT_MESSAGE, SERVER_STOP_MESSAGE, SERVER_SHUTDOWN_MESSAGE, \
    DEFAULT_USERNAME, EMPTY_STRING, TYPE_MATRIX, FAST_API_URL, \
    TYPE_PREMONITIONS
from utils import initiate_logger, tokens_over_used, check_how_many_clients_there_is

logger = initiate_logger()


class ClientState:

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

        self.addr = writer.get_extra_info("peername")

        self.buffer = common.LineBuffer()

        self.username = None

        self.mode = None


class ServerValidator(type):
    """Metaclass that validates network configurations and bind availability on startup."""

    def __init__(cls, name=None, bases=None, dct=None):
        super().__init__(name, bases, dct)

        # 1. Skip validation if it's the base interface/abstract initialization
        if name == "BaseServer":
            return

        # 2. Extract configuration constants from the class definition
        host = dct.get("HOST", EMPTY_STRING)
        port = dct.get("PORT", None)

        # check if the por is valid
        if not isinstance(port, int) or not (1 <= port <= 65535):
            logger.warning(f"Invalid PORT configuration: '{port}'. Must be an integer between 1 and 65535.")

        # 4. Runtime Validation: Try to bind a temporary socket to verify availability
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # Blindly test the binding process
            test_sock.bind((host, port))
            logger.info(f"[Metaclass] Success! {host or 'ANY'}:{port} is available for binding.")
        except (socket.error, OSError) as exc:
            # If the port is in use (Errno 98/48) or access is denied, crash immediately
            logger.warning(f"Metaclass Validation Failed: Cannot bind to {host or 'ANY'}:{port}. "
                           f"Reason: {exc}"
                           )
        finally:
            test_sock.close()  # Clean up the test socket immediately


class AsyncChatServer(object, metaclass=ServerValidator):
    HOST = DEFAULT_HOST
    PORT = 7777

    def __init__(self, port, log_path):
        self.port = port or self.PORT
        self.log_path = log_path
        self.clients = {}  # socket -> ClientState
        self._logger = initiate_logger(self.log_path)
        self.image_db = {}

    # -- setup / teardown -------------------------------------------------

    def close(self):
        """Close all client sockets, the listener, and the log handlers."""
        for state in list(self.clients.values()):
            self._drop(state.write)
        for handler in list(self._logger.handlers):
            handler.flush()
            handler.close()
            self._logger.removeHandler(handler)

    # -- main loop --------------------------------------------------------

    async def run(self):
        server = await asyncio.start_server(
            self.handle_client,
            self.HOST,
            self.port
        )
        self._logger.info(
            "Chat server listening on port %d (logging to %s)",
            self.port,
            self.log_path,
        )

        self._logger.info(SERVER_STOP_MESSAGE)
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

        finally:
            await self._drop(writer)

    async def _dispatch(self, state, message):
        if check_how_many_clients_there_is(self.clients):
            return

        msg_type = message.get("type")
        if message.get("type") == TYPE_HELLO:
            self._logger.info("Client type {}".format(msg_type))
            state.mode = message.get("mode")
            state.username = message.get("username")
            who = state.username or "reader"
            self._logger.info(
                "Client connected: {} ({}) from {}".format(who, state.mode, state.addr[0]))
        elif message.get("type") == TYPE_MSG:
            self._logger.info("Client send {}".format(msg_type))
            await self._handle_chat(state, message.get("text", EMPTY_STRING))
            self._logger.info("Client send text message")
        elif message.get("type") == TYPE_IMAGE:
            full_path = message.get("path")
            self._logger.info("Client send {}".format(msg_type))

            # FAST IN-MEMORY CHECK (O(1) Speed Lookup)
            if full_path in self.image_db:
                self._logger.info(CACHE_HIT_MESSAGE)

                # Pull the pre-calculated, pre-built dictionary from the dictionary DB
                cached_payload = self.image_db[full_path]
                tokens_over_used(self.log_path)

                # Convert it straight to bytes and send it out immediately
                frame = common.encode(cached_payload)
                for other in self.clients.values():
                    if other.mode == MODE_READER:
                        other.writer.write(frame)
                        await other.writer.drain()


            else:
                # Cache MISS: First time seeing this image, process it normally
                self._logger.info(CACHE_MISS_MESSAGE)
                await self._handle_image_path(state, full_path)
        elif message.get("type") == TYPE_MATRIX:
            await self._handle_matrix(state, message.get("content", EMPTY_STRING))
        elif message.get("type") == TYPE_PREMONITIONS:
            await self._handle_premonitions(state, message.get("premonitions", EMPTY_STRING))

    async def _handle_chat(self, state, text):
        """Log an incoming chat line and fan it out to all readers."""
        username = state.username or DEFAULT_USERNAME
        timestamp = datetime.datetime.now().strftime(TIME_FORMAT)

        # DEBUG level so it only goes to the file handler, not stdout.
        self._logger.info("{}, {}, {}".format(username, timestamp, text))

        frame = common.encode(common.make_chat(username, timestamp, "you are good"))
        logger.info("{}".format(frame))

        await self.broadcast(frame)

    async def _handle_image_path(self, state, path):
        """Log an incoming image path and fan it out to all readers."""
        username = state.username or DEFAULT_USERNAME
        timestamp = datetime.datetime.now().strftime(TIME_FORMAT)
        await asyncio.sleep(IMAGE_PROCESSING_DELAY)  # Log it to your system logger file
        self._logger.info("{} shared an image: {} at {}".format(username, path, timestamp))

        # Build the payload mapping exactly what your updated client readers expect
        image_broadcast_payload = common.make_image(path, username)
        image_broadcast_payload["timestamp"] = timestamp
        self._logger.info("{}".format(image_broadcast_payload))
        self.image_db[path] = image_broadcast_payload
        # Encode the frame into bytes.
        # Note: If your common.encode doesn't automatically insert trailing newlines (\n),
        # add + b"\n" here to ensure the client's LineBuffer splits it cleanly.
        frame = common.encode(image_broadcast_payload)

        await self.broadcast(frame)

    async def _handle_matrix(self, state, payload):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    FAST_API_URL,
                    json=payload
            ) as response:
                result = await response.json()

        username = state.username or DEFAULT_USERNAME

        frame = common.encode(
            common.make_matrix(result, username)
        )

        await self.broadcast(frame)

    async def _handle_premonitions(self, state, payload):
        """func get two word and send back premonition
          create 3 different with to do it ."""
        logger.info("the payload {}".format(payload))
        client_output = payload.split()
        word_to_check_one = client_output[0]
        word_to_check_two = client_output[1]
        logger.info("the payload {}".format(client_output))

        random_number = random.randint(1, 2)
        if random_number == 1:
            clean1 = sorted(word_to_check_one.replace(" ", EMPTY_STRING).lower())
            clean2 = sorted(word_to_check_two.replace(" ", EMPTY_STRING).lower())
            result_for_client = clean1 == clean2
            frame = common.encode(result_for_client)
        if random_number == 2:
            clean1 = word_to_check_one.replace(" ", EMPTY_STRING).lower()
            clean2 = word_to_check_two.replace(" ", EMPTY_STRING).lower()
            result_for_client = clean1 == clean2
            frame = common.encode(result_for_client)
        if random_number == 3:
            pass

        await self.broadcast(frame)

    async def broadcast(self, frame):

        for client in self.clients.values():
            logger.info("{}".format(self.clients.items()))

            if client.mode == MODE_READER:
                client.writer.write(frame)

                await client.writer.drain()

    async def _drop(self, writer):
        """Remove and close a client socket."""
        state = self.clients.pop(writer, None)

        if state and state.username:
            self._logger.info("Client disconnected: {} ".format(state.username))

        writer.close()
        await writer.wait_closed()


def parse_args():
    parser = argparse.ArgumentParser(description="Multi-user chat server.")
    parser.add_argument("-p", "--port", type=int, default=7777,
                        help="Port to listen on 7777")
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
