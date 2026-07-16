"""Shared code for the chat server and client.

Holds everything common to both ``server.py`` and ``client.py``:
the default port, the line-based JSON wire protocol, and a small
buffer helper for reassembling messages received over TCP.
"""

import json

from const import (
    _ENCODING, TYPE_HELLO, TYPE_IMAGE, TYPE_CHAT, NEWLINE_BYTES,
    CHAT_LINE_FORMAT, JSON_ERRORS, TYPE_MATRIX, NEWLINE,
    TYPE_PREMONITIONS, TYPE_MSG
)


def encode(obj):
    """Serialise a protocol object to a newline-terminated UTF-8 frame."""
    return (json.dumps(obj) + NEWLINE).encode(_ENCODING)


def make_hello(mode, username=None):
    """Build the handshake message a client sends on connect."""
    return {"type": TYPE_HELLO, "mode": mode, "username": username}


def make_image(image_path, username):
    """Build an image path message frame."""
    return {
        "type": TYPE_IMAGE,
        "path": image_path,
        "username": username
    }


def make_matrix(payload, username):
    """Build a matrix payload frame."""
    return {
        "type": TYPE_MATRIX,
        "content": payload,
        "username": username
    }


def make_premonitions(payload, username):
    """Build a premonitions payload frame."""
    return {
        "type": TYPE_PREMONITIONS,
        "premonitions": payload,
        "username": username
    }


def make_msg(text):
    """Build a chat message sent by a writer client."""
    return {"type": TYPE_MSG, "text": text}


def make_chat(username, timestamp, text):
    """Build a chat message the server broadcasts to readers."""
    return {
        "type": TYPE_CHAT,
        "username": username,
        "timestamp": timestamp,
        "text": text,
    }


def format_chat_line(username, timestamp, text):
    """Human-readable form a reader prints for one chat message."""
    return CHAT_LINE_FORMAT.format(username, timestamp, text)


class LineBuffer(object):
    """Reassembles newline-delimited JSON frames from a TCP byte stream."""

    def __init__(self):
        self._buffer = b""

    def feed(self, data):
        """Add received bytes and return a list of complete messages."""
        self._buffer += data
        messages = []
        while NEWLINE_BYTES in self._buffer:
            line, self._buffer = self._buffer.split(NEWLINE_BYTES, 1)
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line.decode(_ENCODING)))
            except JSON_ERRORS:
                # Ignore malformed frames rather than crash the peer.
                continue
        return messages