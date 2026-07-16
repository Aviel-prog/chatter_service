"""Chat client -- writer, reader, and duplex modes.

A client connects to the chat server in one of three modes:
* Writer (-u USERNAME): reads terminal input and sends it to the server.
* Reader (-r): prints all incoming broadcasts from the server.
* Duplex (-d USERNAME): allows simultaneous reading and writing.
"""

import argparse
import socket
import sys
import threading
from datetime import datetime as dt

import common
from chatter_service.src.const import MODE_DUPLEX
from const import (
    BUFFER_SIZE, LETTER_FILE_PATH, SEND_FILE, SEND_IMAGE, SEND_CHAT, MODE_WRITER,
    MODE_READER, TYPE_IMAGE, DEFAULT_USERNAME, TYPE_CHAT, DEFAULT_HOST, EMPTY_STRING,
    WRITE_MODE, READ_MODE, SEND_MENU, MESSAGE_PROMPT, SERVER_CLOSED_MESSAGE,
    DISCONNECT_MESSAGE, SEND_MATRIX, SEND_PREMONITIONS, TYPE_MATRIX, TYPE_PREMONITIONS
)
from utils import initiate_logger, deliver_timer

logger = initiate_logger()


def connect(server, port, hello_message):
    """Open a blocking TCP connection and send the handshake frame."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server, port))
    sock.sendall(common.encode(hello_message))
    return sock


class ChatWriter:
    def __init__(self, server, port, username=None):
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
        logger.info(f"Connected (writer) as '{self.username}'. Ctrl-C to quit.")
        try:
            while True:
                sending_mode = input(SEND_MENU).strip()
                text = input(MESSAGE_PROMPT).strip()

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
        """Encodes a payload dictionary and sends it directly (common.encode handles newlines)."""
        encoded_frame = common.encode(payload)
        self.sock.sendall(encoded_frame)

    def send_chat(self, text):
        """Sends a standard chat message."""
        payload = common.make_msg(text)
        self._send_frame(payload)
        logger.info("Sent message")

    def send_image(self, text):
        """Sends an image file path frame."""
        payload = common.make_image(text, self.username)
        self._send_frame(payload)
        logger.info(f"Sent image path: {text}")

    def send_file(self, text):
        """Saves message text to a file, then streams it line-by-line to the server."""
        with open(LETTER_FILE_PATH, WRITE_MODE) as f:
            f.write(text)

        with open(LETTER_FILE_PATH, READ_MODE) as f:
            for line in f:
                clean_line = line.strip()
                if clean_line == EMPTY_STRING:
                    continue
                self._send_frame(common.make_msg(clean_line))
        logger.info("File contents streamed successfully.")

    def send_matrix(self, text):
        """Sends a matrix structured frame."""
        payload = common.make_matrix(text, self.username)
        self._send_frame(payload)
        logger.info("Sent Matrix payload")

    def send_premonitions(self, text):
        """Sends a premonition structured frame."""
        payload = common.make_premonitions(text, self.username)
        self._send_frame(payload)
        logger.info("Sent premonitions payload")

    def close(self):
        """Closes the socket cleanly."""
        if self.sock:
            try:
                self.sock.close()
                logger.debug("Socket closed.")
            except OSError:
                pass


class ChatReader:
    def __init__(self, server, port, username=None):
        self.server = server
        self.port = port
        self.username = username or DEFAULT_USERNAME
        self.sock = None
        self.read_map = {
            TYPE_CHAT: self.read_chat,
            TYPE_IMAGE: self.read_image,
            TYPE_MATRIX: self.read_matrix,
            TYPE_PREMONITIONS: self.read_premonitions,
        }

    def run_reader(self, sock=None):
        """Receive broadcast chat messages and process them as they arrive."""
        if sock is None:
            self.sock = connect(self.server, self.port, common.make_hello(MODE_READER, self.username))
        else:
            self.sock = sock

        logger.info("Connected (reader). Showing messages; Ctrl-C to quit.")
        buffer = common.LineBuffer()

        try:
            while True:
                data = self.sock.recv(BUFFER_SIZE)
                if not data:
                    logger.debug("Server closed the connection.")
                    break

                parsed_messages = buffer.feed(data)
                for message in parsed_messages:
                    if isinstance(message, dict):
                        msg_type = message.get("type")
                        handler = self.read_map.get(msg_type)
                        if handler:
                            handler(message)
                        else:
                            # Fallback default handler for unrecognized message payloads
                            logger.info(f"Received unknown frame: {message}")
                    else:
                        logger.info(f"Raw frame data received: {message}")

        except KeyboardInterrupt:
            logger.info(DISCONNECT_MESSAGE)
        except (socket.error, OSError) as exc:
            logger.info(SERVER_CLOSED_MESSAGE.format(exc))
        finally:
            if sock is None and self.sock:
                self.sock.close()

    @staticmethod
    def read_chat(message):
        """Callback to print formal standard chat line broadcasts."""
        logger.info(common.format_chat_line(
            message.get("username", DEFAULT_USERNAME),
            message.get("timestamp", EMPTY_STRING),
            message.get("text", EMPTY_STRING)
        ))

    @staticmethod
    def read_image(payload):
        logger.info(f"[{payload.get('timestamp')}] {payload.get('username')} shared an image path: {payload.get('path')}")

    @staticmethod
    def read_matrix(payload):
        logger.info(f"{payload.get('username')} Matrix response: {payload.get('content')}")

    @staticmethod
    def read_premonitions(payload):
        logger.info(f"{payload.get('username')} Premonitions prediction: {payload.get('premonitions')}")


class ChatWriteAndRead(ChatReader, ChatWriter):
    def __init__(self, server, port, username):
        ChatWriter.__init__(self, server, port, username)
        ChatReader.__init__(self, server, port, username)
        self.running = True


    def run_write_and_read(self):
        """Runs the duplex connection using a background thread for concurrent reading."""
        self.sock = connect(self.server, self.port, common.make_hello(MODE_DUPLEX, self.username))

        # Start background daemon thread for reading so terminal prompt doesn't block
        # reader_thread = threading.Thread(target=self.run_write_and_read, args=(self.sock,), daemon=True)
        # reader_thread.start()

        logger.info(f"Connected (duplex) as '{self.username}'. Begin chatting!")

        try:
            while self.running:
                sending_mode = input(SEND_MENU).strip()
                if sending_mode == EMPTY_STRING or sending_mode not in self.send_map.keys():
                    logger.info("Invalid choice please enter current mode")
                text = input(MESSAGE_PROMPT).strip()
                if text == EMPTY_STRING:
                    continue

                start_deliver_time = dt.now()

                send_func = self.send_map[sending_mode]
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
            self.running = False
            self.close()


def parse_args():
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
            reader = ChatReader(server=args.server, port=args.port)
            reader.run_reader()
        elif args.username:
            writer = ChatWriter(server=args.server, port=args.port, username=args.username)
            writer.run_writer()
        elif args.duplex:
            duplex = ChatWriteAndRead(args.server, args.port, args.duplex)
            duplex.run_write_and_read()
    except (socket.error, OSError) as exc:
        sys.exit("Could not connect to {}, {} -- {}.".format(args.server, args.port, exc))


if __name__ == "__main__":
    main()