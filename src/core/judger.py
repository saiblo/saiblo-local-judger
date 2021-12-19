import asyncio
import concurrent.futures
import signal
import threading
from asyncio import IncompleteReadError
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, IO, Callable

from .exception import JudgerIllegalState
from .logger import LOG
from .protocol import Protocol, RoundConfig, RoundInfo, AiErrorType
from .summary import JudgeSummary
from .utils import bytes2int


class JudgerEvent(Enum):
    TCP_SERVER_STARTED = auto(),
    AI_CONNECTED = auto(),
    NEW_ROUND = auto(),
    GAME_OVER = auto()


class Judger:
    # Judger config
    player_count: int
    output_dir: Path
    replay_path: Path
    logic_path: Path
    config: object
    host: str
    port: int
    # Communication
    to_logic_msg: asyncio.Queue
    to_ai_msg: List[asyncio.Queue]
    logic_proc: asyncio.subprocess.Process
    # Game state
    next_ai_index: int
    listen_target: [int]
    timer: Optional[asyncio.TimerHandle]
    round_time_limit: int
    round_begin_time: float
    output_limit: int
    state: int
    game_running: bool
    # Internal
    server: asyncio.AbstractServer
    shutdown_event: asyncio.Event
    executor: concurrent.futures.ThreadPoolExecutor
    summary: JudgeSummary
    event_handler: Optional[Callable]

    def __init__(self, **kwargs):
        def getValue(name):
            v = kwargs.get(name)
            if v is None:
                LOG.error("Missing init config: %s", name)
                raise JudgerIllegalState
            return v

        self.player_count = getValue("player_count")
        self.output_dir = getValue("output")
        self.replay_path = self.output_dir / "replay.json"
        self.logic_path = getValue("logic_path")
        self.config = getValue("config")
        self.host, self.port = "localhost", getValue("port")

        self.to_ai_msg = []
        self.next_ai_index = 0
        self.listen_target = []
        self.timer = None
        self.round_time_limit = 3
        self.round_begin_time = 0
        self.output_limit = 2048
        self.state = -1
        self.game_running = False
        self.event_handler = None

    # Logic Handlers
    async def handle_logic_stdout(self, stdout):
        LOG.info("Attached to logic stdout")
        try:
            while True:
                pack_size: int = bytes2int(await stdout.readexactly(4))
                target: int = bytes2int(await stdout.readexactly(4))
                data: bytes = await stdout.readexactly(pack_size)
                LOG.debug("Logic is sending %d bytes of data to target %d: %s", pack_size, target, data)
                asyncio.create_task(self.parse_logic_data(target, data))
        except IncompleteReadError:
            LOG.warning("Logic stream reached EOF.")

    async def handle_logic_stderr(self, stderr):
        LOG.info("Attached to Logic stderr")
        loop = asyncio.get_event_loop()
        logic_stderr_path = self.output_dir / "logic_stderr.txt"
        trace_file: IO = await loop.run_in_executor(self.executor, lambda: open(logic_stderr_path, "w"))
        LOG.debug("Logic stderr will also be logged into file: %s", logic_stderr_path)
        try:
            while True:
                line = await stderr.readline()
                if not line:
                    break
                loop.run_in_executor(self.executor, lambda: trace_file.writelines([line.decode("utf-8")]))
                LOG.debug("Logic STDERR: %s", line)
            LOG.info("Logic stderr disconnected normally.")
        except:
            if not self.shutdown_event.is_set():
                LOG.warning("Logic stderr disconnected unexpectedly", exc_info=True)
        finally:
            loop.run_in_executor(self.executor, lambda: trace_file.close())

    async def send_to_logic_stdin(self, stdin):
        LOG.info("Attached to logic stdin")
        while True:
            data: bytes = await self.to_logic_msg.get()
            LOG.debug("Send data to logic: %s", data)
            stdin.write(data)
            await stdin.drain()
            LOG.debug("Send complete")
            self.to_logic_msg.task_done()

    async def wait_logic_exit(self):
        return_code = await self.logic_proc.wait()
        if self.game_running:
            if return_code == 0:
                LOG.warning("Logic exit normally before game over")
            else:
                self.summary.appendLogicCrashed()
                LOG.error("Logic crashed with exit code: %d", return_code)
        self.fire_event({"type": JudgerEvent.GAME_OVER})
        asyncio.create_task(self.__shutdown())

    async def try_launch_logic(self):
        if self.next_ai_index < self.player_count:
            return

        LOG.info("The number of players is sufficient. LINK START!")
        self.logic_proc = await asyncio.create_subprocess_exec(
            str(self.logic_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True
        )

        self.summary.appendLogicBooted()
        self.game_running = True
        self.to_logic_msg = asyncio.Queue()
        await self.to_logic_msg.put(
            Protocol.to_logic_init_info(
                [1 for _ in range(self.player_count)],
                self.config, self.replay_path
            )
        )

        for task in [
            self.send_to_logic_stdin(self.logic_proc.stdin),
            self.handle_logic_stdout(self.logic_proc.stdout),
            self.handle_logic_stderr(self.logic_proc.stderr),
            self.wait_logic_exit(),
        ]:
            asyncio.create_task(task)

    # AI Handlers
    async def read_from_ai(self, reader: asyncio.StreamReader, ai_id: int):
        LOG.info("Attached to AI[id=%d] reader", ai_id)
        try:
            while True:
                pack_size: int = bytes2int(await reader.readexactly(4))

                if pack_size > self.output_limit:
                    self.on_ai_ole(ai_id)
                else:
                    data: bytes = await reader.readexactly(pack_size)
                    LOG.debug("Received %d bytes of data from ai[id=%d]: %s", pack_size, ai_id, data)
                    if self.listen_target.count(ai_id) == 0:
                        LOG.warning("Received data from ai which is not listened")
                    else:
                        LOG.info("Received data from listened ai. Forwarding to logic.")
                        elapsed_time = 1000 * (asyncio.get_running_loop().time() - self.round_begin_time)
                        data = Protocol.to_logic_ai_normal_message(ai_id, data.decode('utf-8'), elapsed_time)
                        asyncio.create_task(self.to_logic_msg.put(data))
        except IncompleteReadError:
            LOG.warning("Reader stream of AI[id=%d] is closed", ai_id)
            if self.game_running:
                self.on_ai_re(ai_id)

    async def write_to_ai(self, writer: asyncio.StreamWriter, ai_id: int):
        LOG.info("Attached to AI[id=%d] writer", ai_id)
        while True:
            data: bytes = await self.to_ai_msg[ai_id].get()
            LOG.debug("Send data to ai[id=%d]: %s", ai_id, data)
            writer.write(data)
            await writer.drain()
            self.to_ai_msg[ai_id].task_done()

    async def wait_ai_writer_closed(self, writer: asyncio.StreamWriter, ai_id: int):
        await writer.wait_closed()
        LOG.warning("Writer stream of AI[id=%d] is closed", ai_id)
        if self.game_running:
            self.on_ai_re(ai_id)

    async def handle_ai_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        LOG.info("A new AI is connected")

        # It is atomic operation?
        ai_id = self.next_ai_index
        self.summary.appendAiConnected(ai_id)
        self.next_ai_index = self.next_ai_index + 1
        self.to_ai_msg.append(asyncio.Queue())
        self.fire_event({"type": JudgerEvent.AI_CONNECTED})

        for task in [
            self.try_launch_logic(),
            self.read_from_ai(reader, ai_id),
            self.write_to_ai(writer, ai_id),
            self.wait_ai_writer_closed(writer, ai_id),
        ]:
            asyncio.create_task(task)

    def on_ai_ole(self, ai_id: int) -> None:
        self.game_running = False
        LOG.warning("AI %d exceeded output limit %d", ai_id, self.output_limit)
        asyncio.create_task(
            self.to_logic_msg.put(Protocol.to_logic_ai_error(ai_id, self.state, AiErrorType.OutputLimitError)))
        self.summary.appendAiOle(self.state, ai_id)

    def on_ai_re(self, ai_id: int) -> None:
        self.game_running = False
        LOG.warning("AI %d disconnected unexpectedly", ai_id)
        asyncio.create_task(self.to_logic_msg.put(Protocol.to_logic_ai_error(ai_id, self.state, AiErrorType.RunError)))
        self.summary.appendAiRe(self.state, ai_id)

    def on_ai_tle(self) -> None:
        self.game_running = False
        if len(self.listen_target) > 0:
            timeout_ai = self.listen_target[0]
            LOG.warning("AI %d listen timeout", timeout_ai)
            asyncio.create_task(
                self.to_logic_msg.put(Protocol.to_logic_ai_error(timeout_ai, self.state, AiErrorType.TimeOutError)))
            self.summary.appendAiTle(self.state, timeout_ai)
        elif self.game_running:
            LOG.warning("Timeout but no listen target set. This may be an internal bug.")

    # Handle state change
    def check_state_change(self, new_state: int) -> None:
        if self.state != new_state:
            if self.timer is not None:
                self.timer.cancel()
            loop = asyncio.get_running_loop()
            self.timer = loop.call_later(self.round_time_limit, self.on_ai_tle)
            current_time = loop.time()
            if self.state == -1:
                elapsed_time = 0
                LOG.info("Enter next round %d", new_state)
            else:
                elapsed_time = current_time - self.round_begin_time
                LOG.info("Enter next round %d. Last round took %f seconds.", new_state, elapsed_time)
            self.state = new_state
            self.round_begin_time = current_time
            self.fire_event({"type": JudgerEvent.NEW_ROUND})
            self.summary.appendNewRound(self.state, elapsed_time)

    # Logic data handler
    async def parse_logic_data(self, target_id: int, data: bytes) -> None:
        if target_id == -1:
            # PyCharm bug which causes confusion on decorated function
            # noinspection PyTypeChecker
            message = Protocol.from_logic_data(data)
            if isinstance(message, RoundConfig):
                LOG.info("Round config received")
                if self.round_time_limit != message.time:
                    LOG.info("Reset round time limit to %s", message.time)
                    self.round_time_limit = message.time
                # We currently ignore length limit
            elif isinstance(message, RoundInfo):
                LOG.info("Normal round information received")
                if len(message.player) != len(message.content):
                    LOG.error("Player count %d is not equal to content count %d. "
                              "Judger will ignore this message currently",
                              len(message.player), len(message.content))
                    return
                self.check_state_change(message.state)
                self.listen_target = message.listen
                LOG.info("Now listening on player %s", str(self.listen_target))

                for i in range(len(message.player)):
                    ai_id = message.player[i]
                    data = message.content[i].encode("utf-8")
                    asyncio.create_task(self.to_ai_msg[ai_id].put(data))
            elif type(message) == list:
                LOG.info("Game over. Result: %s", str(message))
                self.summary.appendGameOver(message)
                self.fire_event({"type": JudgerEvent.GAME_OVER})
                asyncio.create_task(self.__shutdown())
            else:
                LOG.error("Unrecognized logic data: %s. Ignoring.", data.decode("utf-8"))
        elif list(range(self.player_count)).count(target_id):
            LOG.info("Directly forwarding data to AI %d", target_id)
            asyncio.create_task(self.to_ai_msg[target_id].put(data))
        else:
            LOG.error("Invalid target id %d. Ignoring.", target_id)

    def fire_event(self, event: dict):
        if self.event_handler is not None:
            asyncio.get_event_loop().run_in_executor(self.executor, lambda: self.event_handler(**event))

    def set_event_handler(self, handler):
        self.event_handler = handler

    # Main control
    async def run(self) -> JudgeSummary:
        self.executor = concurrent.futures.ThreadPoolExecutor()
        self.shutdown_event = asyncio.Event()
        self.summary = JudgeSummary()

        server = await asyncio.start_server(self.handle_ai_connection, self.host, self.port)
        addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
        self.fire_event({
            "type": JudgerEvent.TCP_SERVER_STARTED,
            "addr": addrs
        })
        LOG.info("Judger server is running at %s", addrs)
        asyncio.create_task(server.serve_forever())

        self.server = server
        loop = asyncio.get_event_loop()

        def signal_handler():
            self.summary.appendInternalError()
            asyncio.create_task(self.__shutdown())

        if threading.current_thread() is threading.main_thread():
            for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(s, signal_handler)

        await self.shutdown_event.wait()
        return self.summary

    def start(self) -> JudgeSummary:
        summary = asyncio.run(self.run())
        LOG.info("SaibloLocalJudger is closed")
        return summary

    def shutdown(self):
        asyncio.create_task(self.__shutdown())

    async def __shutdown(self):
        LOG.info("SaibloLocalJudger is shutting down")
        self.server.close()
        self.shutdown_event.set()
