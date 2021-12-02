import logging
import sys
from logging import Logger
from typing import Optional


def get_logger() -> Logger:
    def init_logger(logger: Optional[Logger] = None):
        if logger is None:
            logger = logging.getLogger("SLJ Core")
            logger.setLevel(logging.DEBUG)
            ch = logging.StreamHandler(stream=sys.stdout)
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(module)s:%(lineno)s | %(message)s")
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    return init_logger()
