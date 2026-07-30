"""日志系统"""

import logging
import os

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_logger = logging.getLogger("gesture")
_logger.setLevel(logging.DEBUG)

fmt = logging.Formatter("[%(asctime)s] %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

fh = logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(fmt)
_logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(fmt)
_logger.addHandler(ch)


def get_logger():
    return _logger
