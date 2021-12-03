import logging
import sys
from logging import Logger
from pathlib import Path
from typing import Optional

_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(module)s:%(lineno)s | %(message)s")


def get_logger() -> Logger:
    def init_logger(logger: Optional[Logger] = None):
        if logger is None:
            logger = logging.getLogger("SLJ Core")
            logger.setLevel(logging.DEBUG)
            ch = logging.StreamHandler(stream=sys.stdout)
            ch.setLevel(logging.INFO)
            ch.setFormatter(_formatter)
            logger.addHandler(ch)
        return logger

    return init_logger()


def set_log_output_file(output_dir: Path) -> None:
    logger = get_logger()
    file = output_dir / "judger.log"
    file_handler = logging.FileHandler(file)
    file_handler.setFormatter(_formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.debug("Logging to file %s is successfully enabled", file)
