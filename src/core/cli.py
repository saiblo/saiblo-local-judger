import argparse
import json
import os.path
import random
from json import JSONDecodeError

from .judger import Judger
from .logger import get_logger

log = get_logger()


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
    protocol_version = args.protocolVesion

    config = {}
    if config_file:
        try:
            with open(config_file, "r") as configFilePtr:
                config = json.load(configFilePtr)
        except IOError:
            log.exception("Failed to access config file %s", config_file)
            exit(1)
        except JSONDecodeError:
            log.exception("Failed to parse json in config file [{}]".format(config_file))
            exit(1)

    if not output:
        output = "res-{:010d}".format(random.randrange(0, 10000000000))

    if not os.path.exists(output):
        os.makedirs(output)

    if not os.path.isdir(output):
        log.error("Output should be a directory")
        exit(1)

    judger_config = {
        "port": port,
        "player_count": player_count,
        "config": config,
        "output": output,
        "logic_path": logic_path,
        "protocol_version": protocol_version
    }
    log.info("Starting local judger with config[%s]", judger_config)
    Judger(**judger_config).start()
