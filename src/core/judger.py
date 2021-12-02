import socketserver
import threading
from logging import Logger
from pathlib import Path
from socketserver import ThreadingTCPServer
from typing import List, Optional

from .comm import AICommunicationChannel, LogicCommunicationChannel
from .logger import get_logger
from .protocol import Protocol, RoundConfig, RoundInfo, AiErrorType

log: Logger = get_logger()


class Judger:
    # Judger config
    player_count: int
    output_dir: str
    replay_path: str
    logic_path: str
    config: object
    # Communication
    server: ThreadingTCPServer
    players: List[AICommunicationChannel]
    logic: LogicCommunicationChannel
    # Game state
    listen_target: [int]
    timer: Optional[threading.Timer]
    round_time_limit: int
    output_limit: int
    state: int

    def __init__(self, **kwargs):
        def getValue(name):
            v = kwargs.get(name)
            if v is None:
                log.error("Missing init config: %s", name)
                exit(1)
            return v

        self.player_count = getValue("player_count")
        self.output_dir = getValue("output")
        self.replay_path = str(Path(getValue("output")) / "replay.json")
        self.logic_path = getValue("logic_path")
        self.config = getValue("config")

        self.listen_target = []
        self.round_time_limit = 3
        self.output_limit = 2048
        self.state = -1

        def initHandler(*args) -> socketserver.BaseRequestHandler:
            player_id = len(self.players)
            handler = AICommunicationChannel(
                lambda data: self.__on_ai_data(player_id, data),
                lambda: self.__on_ai_ole(player_id),
                lambda: self.__on_ai_closed(player_id),
                *args)
            self.players.append(handler)
            if len(self.players) == self.player_count:
                self.__start_game()
            return handler.run()

        host, port = "localhost", getValue("port")
        self.server = ThreadingTCPServer((host, port), initHandler)
        self.players = []

    def get_output_limit(self) -> int:
        return self.output_limit

    def __on_ai_data(self, ai_id: int, data: bytes) -> None:
        if self.listen_target.count(ai_id) == 0:
            log.warning("Received data from ai which is not listened.")
        else:
            log.info("Received data from listened ai. Forwarding to logic.")
            self.logic.send(data)

    def __on_ai_ole(self, ai_id: int) -> None:
        self.logic.send(Protocol.to_logic_ai_error(ai_id, self.state, AiErrorType.OutputLimitError))

    def __on_ai_closed(self, ai_id: int) -> None:
        self.logic.send(Protocol.to_logic_ai_error(ai_id, self.state, AiErrorType.RunError))

    def __check_state_change(self, new_state: int) -> None:
        if self.state != new_state:
            log.info("Enter next round %d", new_state)
            if self.timer is not None:
                self.timer.cancel()
            self.timer = threading.Timer(self.round_time_limit, self.__round_timeout)

    def __on_logic_data(self, target_id: int, data: bytes) -> None:
        if target_id == -1:
            # PyCharm bug which causes confusion on decorated function
            # noinspection PyTypeChecker
            message = Protocol.from_logic_data(data)
            if isinstance(message, RoundConfig):
                log.info("Round config received")
                if self.round_time_limit != message.time:
                    log.info("Resetting round time limit to %s", message.time)
                    self.round_time_limit = message.time
                self.__check_state_change(message.state)
                # We currently ignore length limit
            elif isinstance(message, RoundInfo):
                log.info("Normal round information received")
                self.__check_state_change(message.state)
                log.info("Now listening on player %s", str(message.listen))
                if len(message.player) != len(message.content):
                    log.error("Player count %d is not equal to content count %d", len(message.player),
                              len(message.content))
                for i in range(len(message.player)):
                    ai_id = message.player[i]
                    self.players[ai_id].send(message.content[i].encode("utf-8"))
            elif type(message) == list:
                log.info("Game over. Result: %s", str(message))
                self.shutdown()
            else:
                log.error("Unrecognized logic data type: %s", data.decode("utf-8"))
                raise ValueError
        elif list(range(self.player_count)).count(target_id):
            log.info("Directly forwarding data to AI %d", target_id)
            self.players[target_id].send(data)
        else:
            log.error("Invalid target id %d", target_id)
            raise ValueError

    def __start_game(self) -> None:
        self.logic = LogicCommunicationChannel(self.__on_logic_data, self.output_dir, self.logic_path)
        self.logic.send(
            Protocol.to_logic_init_info([1 for _ in range(self.player_count)], self.config, self.replay_path))

    def __round_timeout(self) -> None:
        if len(self.listen_target) > 0:
            timeout_ai = self.listen_target[0]
            log.warning("AI %d listen timeout", timeout_ai)
            self.logic.send(Protocol.to_logic_ai_error(timeout_ai, self.state, AiErrorType.TimeOutError))
        else:
            log.warning("Timeout but no listen target set. This may be an internal bug.")

    def start(self):
        ip, port = self.server.server_address
        log.info("Judger server is running at %s:%d", ip, port)
        self.server.serve_forever()

    def shutdown(self):
        log.info("Judger server is shutting down")
        if self.timer is not None:
            self.timer.cancel()
        self.logic.close()
        self.server.shutdown()
