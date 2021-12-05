import logging
import sys
from pathlib import Path

_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(module)s:%(lineno)s | %(message)s")


def _init_logger():
    logger = logging.getLogger("SLJ Core")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(_formatter)
    logger.addHandler(ch)
    return logger


LOG = _init_logger()


def set_log_output_file(output_dir: Path) -> None:
    file = output_dir / "judger.log"
    file_handler = logging.FileHandler(file)
    file_handler.setFormatter(_formatter)
    file_handler.setLevel(logging.DEBUG)
    LOG.addHandler(file_handler)
    LOG.debug("Logging to file %s is successfully enabled", file)
