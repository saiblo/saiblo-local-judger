import argparse
import json
import random
import sys
from json import JSONDecodeError
from pathlib import Path

from .exception import JudgerIllegalState
from .judger import Judger
from .logger import LOG, set_log_output_file

version = "v0.0.1-alpha"


def main():
    parser = argparse.ArgumentParser(prog="python -m core", description="CLI for SaibloLocalJudger Core")
    parser.add_argument("--port", type=int, help="Tcp server listening port. Default port is random.", default=0)
    parser.add_argument("--playerCount", type=int, help="Required. Count of players to start a game.")
    parser.add_argument("--configFile", type=str, help="Game config file.")
    parser.add_argument("--output", type=str, help="Output directory.")
    parser.add_argument("--logicPath", type=str, help="Required. Path to logic executable.")
    parser.add_argument("--protocolVersion", type=int, help="Communication protocol version.", default=1)
    args = parser.parse_args()

    def require_not_none(x):
        if x is None:
            parser.print_usage()
            exit(1)
        return x

    port = args.port
    player_count = require_not_none(args.playerCount)
    config_file = args.configFile
    output = args.output
    logic_path = require_not_none(args.logicPath)
    protocol_version = args.protocolVersion

    config = {}
    if config_file:
        try:
            with open(config_file, "r") as configFilePtr:
                config = json.load(configFilePtr)
        except IOError:
            LOG.exception("Failed to access config file %s", config_file)
            exit(1)
        except JSONDecodeError:
            LOG.exception("Failed to parse json in config file [{}]".format(config_file))
            exit(1)

    if not output:
        output = "res-{:010d}".format(random.randrange(0, 10000000000))

    output_dir = Path.cwd() / output
    # Make sure output directory is existed
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except IOError:
        LOG.exception("Cannot access output directory")
        exit(1)

    set_log_output_file(output_dir)

    LOG.info("SaibloLocalJudger %s", version)

    # Register global exception.py handler
    def exception_handler(exctype, value, traceback):
        if exctype == JudgerIllegalState:
            LOG.fatal("SaibloLocalJudger is existing due to unrecoverable illegal state. "
                      "Please check the log to find the reason.")
        else:
            LOG.fatal("SaibloLocalJudger crashed unexpectedly. Please report this issue.")
            sys.__excepthook__(exctype, value, traceback)
        sys.exit(1)

    sys.excepthook = exception_handler

    judger_config = {
        "port": port,
        "player_count": player_count,
        "config": config,
        "output": output_dir,
        "logic_path": Path.cwd() / logic_path,
        "protocol_version": protocol_version
    }
    LOG.info("Launching local judger with config[%s]", judger_config)
    summary = Judger(**judger_config).start()
    LOG.info("Judger existed. Summary:")
    LOG.info("%s", summary)
