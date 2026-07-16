import logging
import statistics
import sys
import socket

from const import DEFAULT_LOG_FILE_PATH, LOGGER_NAME, FILE_LOG_FORMAT, CONSOLE_LOG_FORMAT, TOKEN_WARNING_THRESHOLD, \
    MSG_TOKEN_ALERT, READ_MODE, MAX_CLIENTS, MILLISECONDS_PER_SECOND, EMPTY_STRING


def initiate_logger(log_path=DEFAULT_LOG_FILE_PATH):
    """Configure and return the logger used for chat traffic.

    Chat lines are written as CSV rows to ``log_path`` at DEBUG level
    (so every message is persisted), while INFO-and-above records
    (connect/disconnect notices, server status, etc.) are also echoed
    to stdout.
    """
    _logger = logging.getLogger(LOGGER_NAME)
    _logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if this is ever called more than once.
    if _logger.handlers:
        return _logger

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)  # debug (chat rows) and up to file
    file_handler.setFormatter(logging.Formatter(FILE_LOG_FORMAT))
    _logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Screen will show INFO, WARNING, ERROR (skips raw DEBUG)
    console_formatter = logging.Formatter(CONSOLE_LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    _logger.addHandler(console_handler)

    return _logger


logger = initiate_logger()


def tokens_over_used(file_path):
    counter = 0
    target_phrase = "Cache HIT: Image path found in memory. Broadcasting instantly."
    with open(file_path, READ_MODE) as f:
        for line in f:

            if target_phrase in line.strip():
                counter += 1

            if counter >= TOKEN_WARNING_THRESHOLD:
                logger.info(MSG_TOKEN_ALERT)
                break


@staticmethod
def check_how_many_clients_there_is(clients_dict):
    """Static utility to check client limits and log warnings."""
    count_of_client = len(clients_dict)
    if count_of_client >= MAX_CLIENTS:
        logger.warning("there are more than 19 clients, its too much")
        return True  # Returns True indicating the server is full
    return False  # Returns False indicating there is still room


def deliver_timer(start_time, end_time):
    all_duration = []
    duration = end_time - start_time
    milliseconds_taken = duration.total_seconds() * MILLISECONDS_PER_SECOND
    all_duration.append(milliseconds_taken)
    current_duration = statistics.median(all_duration)
    logger.debug(f"Sent message successfully. Latency: {current_duration:.2f} ms")

class PortValidator(type):
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
            logger.debug(f" Success! {host or 'ANY'}:{port} is available for binding.")
        except (socket.error, OSError) as exc:
            # If the port is in use (Errno 98/48) or access is denied, crash immediately
            logger.warning(f"Metaclass Validation Failed: Cannot bind to {host or 'ANY'}:{port}. "
                           f"Reason: {exc}"
                           )
        finally:
            test_sock.close()  # Clean up the test socket immediately
