# global const ----------------------------------------------------------------
TYPE_IMAGE = "/image"
TYPE_CHAT = "chat"
TYPE_MSG = "msg"
TYPE_MATRIX = "matrix"
TYPE_PREMONITIONS = "premonitions"

NEWLINE = "\n"
NEWLINE_BYTES = b"\n"
DEFAULT_LOG_FILE_PATH = "log.csv"
EMPTY_STRING = ""

BUFFER_SIZE = 4096
DEFAULT_HOST = "127.0.0.1"
MODE_WRITER = "writer"
MODE_READER = "reader"
MODE_DUPLEX = "duplex"
DEFAULT_USERNAME = "anonymous"
READ_MODE = "r"

# client const ----------------------------------------------------------------

SEND_CHAT = "1"
SEND_FILE = "2"
SEND_IMAGE = "3"
SEND_MATRIX = "4"
SEND_PREMONITIONS = "5"
LETTER_FILE_PATH = "letter"

DEFAULT_TIMESTAMP = "Just now"

WRITE_MODE = "w"

SEND_MENU = (
    "\n"
    "================ Chat Menu ================\n"
    "1. Chat         → send a normal message\n"
    "2. File         → send text from a file\n"
    "3. Image        → send an image path (/image <path>)\n"
    "4. Matrix       → send a matrix operation (JSON format)\n"
    "                 Example: {\"matrix\": [[1,2],[3,4]], \"command\": \"transpose\"}\n"
    "5. Premonition  → compare two words separated by a space\n"
    "============================================\n"
    "Choose an option: "
)
MESSAGE_PROMPT = "Enter your message: "
DISCONNECT_MESSAGE = "\nDisconnecting..."
SERVER_CLOSED_MESSAGE = "Server closed the connection."

# payload = {
#     "matrix": [
#         [1.0, 2.0],
#         [3.0, 4.0]
#     ],
#     "command": "transpose"
# }
# server consts ----------------------------------------------------------------

FAST_API_URL ="http://127.0.0.1:8000/matrix/process"

MAX_PENDING_CONNECTIONS = 20

IMAGE_PROCESSING_DELAY = 10

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

READER_NAME = "reader"

CACHE_HIT_MESSAGE = "Cache HIT: Image path found in memory. Broadcasting instantly."
CACHE_MISS_MESSAGE = "Cache MISS: New image path. Processing..."

CONNECTION_SUCCESS_MESSAGE = "connection successfully"
SERVER_STOP_MESSAGE = "Press Ctrl-C to stop."
SERVER_SHUTDOWN_MESSAGE = "\nShutting down..."

# common consts ----------------------------------------------------------------

_ENCODING = "utf-8"
TYPE_HELLO = "hello"
CHAT_LINE_FORMAT = "[{0}] {1}: {2}"
JSON_ERRORS = (ValueError, UnicodeDecodeError)

# utils consts ----------------------------------------------------------------

FILE_LOG_FORMAT = "%(asctime)s - %(message)s"
CONSOLE_LOG_FORMAT = "[%(levelname)s] %(message)s"
LOGGER_NAME = "chat"
TOKEN_WARNING_THRESHOLD = 2

CACHE_HIT_PHRASE = "Cache HIT: Image path found in memory. Broadcasting instantly."

MSG_TOKEN_ALERT = "high token usage!!"

MAX_CLIENTS = 20
MILLISECONDS_PER_SECOND = 1000

# ------------------------------------------------------------------------------
