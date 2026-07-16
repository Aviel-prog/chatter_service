import logging
import statistics
import sys

from const import DEFAULT_LOG_FILE_PATH, LOGGER_NAME, FILE_LOG_FORMAT, CONSOLE_LOG_FORMAT, TOKEN_WARNING_THRESHOLD, \
    MSG_TOKEN_ALERT, READ_MODE, MAX_CLIENTS, MILLISECONDS_PER_SECOND


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
    logger.info(f"[Metrics] Sent message successfully. Latency: {current_duration:.2f} ms")
