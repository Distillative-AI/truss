import json
import logging
import sys
from datetime import datetime
from enum import Enum

import loguru
from pythonjsonlogger import jsonlogger

LEVEL: int = logging.INFO


class Lifecycle(Enum):
    LOAD = "MODEL_LOAD"
    STARTUP = "MODEL_STARTUP"
    REQUEST = "REQUEST"


def serialize(record):
    dt = datetime.fromtimestamp(record["time"].timestamp())
    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]

    request_id = (
        str(record["extra"]["request_id"]) if "request_id" in record["extra"] else None
    )
    lifecycle = (
        record["extra"]["lifecycle"].value if "lifecycle" in record["extra"] else None
    )
    subset = {
        "asctime": formatted_time,
        "message": record["message"],
        "levelname": record["level"].name,
        "request_id": request_id,
        "lifecycle": lifecycle,
    }

    return json.dumps(subset)


def patching(record):
    # we should be able to label different types of logs here
    record["extra"]["serialized"] = serialize(record)


loguru_logger = loguru.logger

# reset the logger
loguru_logger.remove()

# we want to add request ids via a patch (think of it a middleware)
loguru_logger = loguru_logger.patch(patching)
loguru_logger.add(sys.stdout, format="{extra[serialized]}")


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, stream):
        self.logger = loguru_logger
        self.log_buffer = ""
        self.stream = stream

    def write(self, buf):
        # If we encounter a newline, then log with the buffer and a newline
        if buf.endswith("\n"):
            buf = buf[:-1]
            self.log_buffer += buf

            # log + clear buf
            self.logger.info(self.log_buffer)
            self.log_buffer = ""
        else:
            # If the buffer does not end in a newline, add it to the log buffer for later output
            # we're not going to end up here unless the user overrides print
            self.log_buffer += buf

    def isatty(self):
        return self.stream.isatty()

    def flush(self):
        pass


sys.stdout = StreamToLogger(sys.__stdout__)  # type: ignore
sys.stderr = StreamToLogger(sys.__stderr__)  # type: ignore

JSON_LOG_HANDLER = logging.StreamHandler(stream=sys.stdout)
JSON_LOG_HANDLER.set_name("json_logger_handler")
JSON_LOG_HANDLER.setLevel(LEVEL)
JSON_LOG_HANDLER.setFormatter(
    jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(message)s %(request_id)s")
)


def setup_logging() -> None:
    loggers = [logging.getLogger()] + [
        logging.getLogger(name) for name in logging.root.manager.loggerDict
    ]

    for logger in loggers:
        logger.setLevel(LEVEL)
        logger.propagate = False

        setup = False

        # let's not thrash the handlers unnecessarily
        for handler in logger.handlers:
            if handler.name == JSON_LOG_HANDLER.name:
                setup = True

        if not setup:
            logger.handlers.clear()
            logger.addHandler(JSON_LOG_HANDLER)

    # clear uvicorn loggers so we can overwrite
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.error").handlers = []
