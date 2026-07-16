"""Chat client -- writer and reader modes.

A client connects to the chat server in exactly one of two modes, which
keeps each program single-purpose and avoids the need for threads:

* Writer (``-u USERNAME``): reads lines the user types and sends each
  one to the server as a chat message.
* Reader (``-r``): prints every chat message the server broadcasts,
  including the sender's username and the date+time.

Either way, the user quits by pressing Ctrl-C.

Usage::

    client.py [-u USERNAME] [-r] [-s SERVER] [-p PORT]

    -u USERNAME   Operate in writer mode, using USERNAME
    -r            Operate in reader mode
    -s SERVER     Server address or host name (default: localhost)
    -p PORT       Port to connect to (default: 7777)
"""

import argparse
import socket
import sys
import threading
from datetime import datetime as dt

import common
from const import BUFFER_SIZE, LETTER_FILE_PATH, SEND_FILE, SEND_IMAGE, SEND_CHAT, MODE_WRITER, \
    MODE_READER, TYPE_IMAGE, DEFAULT_USERNAME, TYPE_CHAT, DEFAULT_HOST, EMPTY_STRING, WRITE_MODE, READ_MODE, \
    SEND_MENU, MESSAGE_PROMPT, SERVER_CLOSED_MESSAGE, DISCONNECT_MESSAGE, SEND_MATRIX, NEWLINE_BYTES, SEND_PREMONITIONS, \
    TYPE_MATRIX, TYPE_PREMONITIONS
from utils import initiate_logger, deliver_timer

logger = initiate_logger()


def connect(server, port, hello_message):
    """Open a blocking TCP connection and send the handshake frame."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"DEBUG: server={server} (type: {type(server)}), port={port} (type: {type(port)})")
    sock.connect((server, port))
    sock.sendall(common.encode(hello_message))
    return sock


class ChatWriter:
    def __init__(self, server, port, username):
        self.server = server
        self.port = port
        self.username = username or DEFAULT_USERNAME
        self.sock = None
        self.send_map = {
            SEND_CHAT: self.send_chat,
            SEND_IMAGE: self.send_image,
            SEND_FILE: self.send_file,
            SEND_MATRIX: self.send_matrix,
            SEND_PREMONITIONS: self.send_premonitions
        }

    def run_writer(self):
        """Starts the connection and enters the interactive sending loop."""
        self.sock = connect(self.server, self.port, common.make_hello(MODE_WRITER, self.username))

        # Map transmission menu options to their respective sender methods

        try:
            while True:
                sending_mode = input(SEND_MENU)
                text = input(MESSAGE_PROMPT)

                if text == EMPTY_STRING:
                    continue

                start_deliver_time = dt.now()

                # Find the right method dynamically and call it
                send_func = self.send_map.get(sending_mode)
                if send_func:
                    send_func(text)
                else:
                    logger.warning(f"Unknown sending mode: {sending_mode}")

                end_deliver_time = dt.now()
                deliver_timer(start_deliver_time, end_deliver_time)

        except (EOFError, KeyboardInterrupt):
            logger.info("\nDisconnecting cleanly...")
        except (socket.error, OSError) as exc:
            logger.error(f"\nConnection lost: {exc}")
        finally:
            self.close()

    def _send_frame(self, payload):
        """Encodes a payload dictionary, appends a protocol newline, and sends it."""
        encoded_frame = common.encode(payload) + NEWLINE_BYTES
        self.sock.sendall(encoded_frame)

    # ==========================================
    # SENDING FUNCTIONS
    # ==========================================

    def send_chat(self, text):
        """Sends a standard chat message."""
        payload = common.make_msg(text)
        self._send_frame(payload)
        logger.info("Sent message")

    def send_image(self, text):
        """Sends an image file path frame."""
        payload = common.make_image(text, self.username)
        self._send_frame(payload)
        logger.info(f"Sent image: {text}")

    def send_file(self, text):
        """Saves message text to a file, then streams it line-by-line to the server."""
        # 1. Write incoming text to local buffer file
        with open(LETTER_FILE_PATH, WRITE_MODE) as f:
            f.write(text)

        # 2. Read and stream line by line
        with open(LETTER_FILE_PATH, READ_MODE) as f:
            for line in f:
                clean_line = line.strip()
                if clean_line == EMPTY_STRING:
                    continue
                self._send_frame(common.make_msg(clean_line))
        logger.info("File written and contents completely sent")

    def send_matrix(self, text):
        """Sends a matrix structured frame."""
        payload = common.make_matrix(text, self.username)
        self._send_frame(payload)
        logger.info("Sent Matrix")

    def send_premonitions(self, text):
        """Sends a premonition structured frame."""
        payload = common.make_premonitions(text, self.username)
        self._send_frame(payload)
        logger.info("Sent premonitions")

    # ==========================================
    # MAIN LOOP RUNNER
    # ==========================================

    def close(self):
        """Closes the socket cleanly."""
        if self.sock:
            try:
                self.sock.close()
                logger.debug("Socket closed.")
            except OSError:
                pass


class ChatReader:
    def __init__(self, server, port, username):
        self.server = server
        self.port = port
        self.username = username or DEFAULT_USERNAME
        self.sock = None
        self.read_map = {
            TYPE_CHAT: self.read_chat,
            TYPE_IMAGE: self.read_general,
        }

    def run_reader(self):
        """Receive broadcast chat messages and print them as they arrive."""
        sock = connect(self.server, self.port, common.make_hello(MODE_READER))
        logger.info("Connected (reader). Showing messages; Ctrl-C to quit.")
        buffer = common.LineBuffer()
        try:
            while True:
                data = sock.recv(BUFFER_SIZE)
                if not data:
                    logger.debug("Server closed the connection.")
                    break
                for message in buffer.feed(data):
                    type_of_reading = message.get("type")
                    # Handle traditional text messages
                    read_func = self.read_map(type_of_reading)
                    read_func(data)
        except KeyboardInterrupt:
            logger.info(DISCONNECT_MESSAGE)

        except (socket.error, OSError) as exc:
            logger.info(SERVER_CLOSED_MESSAGE.format(exc))
        finally:
            sock.close()

    def read_chat(self, message):
        logger.info("{}".format(message))
        logger.info(common.format_chat_line(
            message.get("username", DEFAULT_USERNAME),
            message.get("timestamp", EMPTY_STRING),
            message.get("text", EMPTY_STRING)))

    def read_general(self, payload):
        logger.info("shared an image path: {}".format(payload))
        logger.info("Matix results: {}".format(payload))
        logger.info("premonitions results: {}".format(payload))


class ChatWriteAndRead(ChatReader, ChatWriter):
    def __init__(self, server, port, username):
        ChatWriter.__init__(
            self,
            server,
            port,
            username
        )

        ChatReader.__init__(
            self,
            server,
            port,
            username
        )

    def run_writeAndread(self):
        """Starts the connection and enters the interactive sending loop."""
        self.sock = connect(self.server, self.port, common.make_hello(MODE_WRITER, self.username))

        # Map transmission menu options to their respective sender methods
        try:
            while True:
                sending_mode = input(SEND_MENU)
                text = input(MESSAGE_PROMPT)

                if text == EMPTY_STRING:
                    continue

                start_deliver_time = dt.now()

                # Find the right method dynamically and call it
                send_func = self.send_map.get(sending_mode)
                if send_func:
                    send_func(text)
                    self.run_reader()
                else:
                    logger.warning(f"Unknown sending mode: {sending_mode}")

                end_deliver_time = dt.now()
                deliver_timer(start_deliver_time, end_deliver_time)

        except (EOFError, KeyboardInterrupt):
            logger.info("\nDisconnecting cleanly...")
        except (socket.error, OSError) as exc:
            logger.error(f"\nConnection lost: {exc}")
        finally:
            self.close()


def parse_args():  # TODO fix the format
    parser = argparse.ArgumentParser(description="Chat client.")
    parser.add_argument("-u", "--username",
                        help="Operate in writer mode, using USERNAME")
    parser.add_argument("-r", "--reader", action="store_true",
                        help="Operate in reader mode")
    parser.add_argument("-d", "--duplex",
                        help="Operate in duplex mode (read AND write), using USERNAME")
    parser.add_argument("-s", "--server", default=DEFAULT_HOST,
                        help="Server address or host name (default: localhost)")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=7777,
        help="Port to connect to (default: %(default)s)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    modes_selected = sum([bool(args.reader), bool(args.username), bool(args.duplex)])
    if modes_selected != 1:
        sys.exit("Error: Specify exactly one mode: -u USERNAME (writer), -r (reader), or -d USERNAME (duplex).")

    try:
        if args.reader:
            reader = ChatReader(args.server, args.port)
            reader.run_reader()
        elif args.username:
            writer = ChatWriter(server=args.server, port=args.port, username=args.username)
            # Start connecting and typing!
            writer.run_writer()
        elif args.duplex:
            duplex = ChatWriteAndRead(args.server, args.port, args.duplex)
            duplex.run_writeAndread()
    except (socket.error, OSError) as exc:
        sys.exit("Could not connect to {}, {} -- {}.".format(args.server, args.port, exc))


if __name__ == "__main__":
    main()
