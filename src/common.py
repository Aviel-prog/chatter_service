"""Shared code for the chat server and client.

Holds everything common to both ``server.py`` and ``client.py``:
the default port, the line-based JSON wire protocol, and a small
buffer helper for reassembling messages received over TCP.

Wire protocol
-------------
Every protocol unit is a single JSON object encoded as UTF-8 and
terminated by a newline (``\\n``).  Using one JSON object per line lets
chat text contain arbitrary characters (spaces, punctuation, etc.)
without us having to invent an escaping scheme for a field separator.

Message types
~~~~~~~~~~~~~
* hello  -- sent by a client right after connecting, announcing its
            mode ("writer" or "reader") and (for writers) its username.
* msg    -- sent by a writer client, carrying one line of chat text.
* chat   -- sent by the server to every reader, carrying the username,
            timestamp and text of a chat message.
"""

import json

from const import _ENCODING, TYPE_HELLO, TYPE_IMAGE, TYPE_CHAT, NEWLINE_BYTES, CHAT_LINE_FORMAT, \
    JSON_ERRORS, TYPE_MATRIX, NEWLINE, TYPE_PREMONITIONS, TYPE_MSG


def encode(obj):
    """Serialise a protocol object to a newline-terminated UTF-8 frame."""
    return (json.dumps(obj) + NEWLINE).encode(_ENCODING)


def make_hello(mode, username=None, ):
    """Build the handshake message a client sends on connect."""
    return {"type": TYPE_HELLO, "mode": mode, "username": username}


def make_image(image_path, username):
    return {"type": TYPE_IMAGE,  # Custom message type for your server to identify
            "path": image_path,
            "username": username
            }


def make_matrix(payload, username):
    return {"type": TYPE_MATRIX,  # Custom message type for your server to identify
            "content": payload,
            "username": username
            }


def make_premonitions(payload, username):
    return {"type": TYPE_PREMONITIONS,  # Custom message type for your server to identify
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
    return CHAT_LINE_FORMAT.format(timestamp, username, text)


class LineBuffer(object):
    """Reassembles newline-delimited JSON frames from a TCP byte stream.

    TCP is a stream, so a single ``recv`` may return part of a frame,
    exactly one frame, or several frames at once.  Feed raw bytes in
    with :meth:`feed` and get back the list of complete protocol
    objects that have arrived so far; any trailing partial frame is
    kept until the rest of it shows up.
    """

    def __init__(self):
        self._buffer = NEWLINE_BYTES

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
