import socket
import socketserver
import subprocess
import threading
from logging import Logger
from pathlib import Path
from typing import Callable, TextIO

from .exception import JudgerIllegalState
from .logger import get_logger
from .utils import bytes2int

log: Logger = get_logger()

Callback = Callable[[], None]
BytesConsumer = Callable[[bytes], None]
IntProvider = Callable[[], int]
IntBytesConsumer = Callable[[int, bytes], None]


class SocketHandler(socketserver.StreamRequestHandler):
    on_receive: BytesConsumer
    on_ole: Callback
    on_closed: Callback
    output_limit_provider: IntProvider

    def __init__(self, on_receive: BytesConsumer, on_ole: Callback, on_closed: Callback,
                 output_limit_provider: IntProvider, *args):
        super().__init__(*args)
        self.on_receive = on_receive
        self.on_ole = on_ole
        self.on_closed = on_closed
        self.output_limit_provider = output_limit_provider

    def handle(self) -> None:
        log.info("Handling AI connection from %s", self.client_address)
        try:
            while True:
                pack_size = bytes2int(self.rfile.read(4))
                output_limit = self.output_limit_provider()
                if pack_size > output_limit:
                    log.error("AI exceeded output limit: %d > %d", pack_size, output_limit)
                    self.on_ole()
                    return

                data = self.rfile.read(pack_size)
                log.debug("Received data from %s: %s", self.client_address, data.decode("utf-8"))
                self.on_receive(data)
        except socket.error:
            log.warning("Judger cannot read data from AI Channel. It is closed unexpectedly.", exc_info=True)
            self.on_closed()

    def send(self, data: bytes) -> None:
        log.debug("Sending data to %s: %s", self.client_address, data.decode("utf-8"))
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except socket.error:
            log.warning("Judger cannot send data to AI Channel. It is closed unexpectedly.", exc_info=True)
            self.on_closed()


class AICommunicationChannel:
    socket: SocketHandler
    args: any

    def __init__(self, *args):
        self.args = args

    def run(self) -> SocketHandler:
        self.socket = SocketHandler(*self.args)
        return self.socket

    def send(self, data: bytes):
        self.socket.send(data)


class LogicCommunicationChannel:
    logic_proc: subprocess.Popen
    output_dir: str
    running: bool
    stderr_thread: threading.Thread
    stderr_file: TextIO
    stdout_thread: threading.Thread
    on_receive: IntBytesConsumer

    def __init__(self, on_receive: IntBytesConsumer, output_dir: str, logic_path: str):
        log.info("Try to open logic with %s", logic_path)

        self.output_dir = output_dir
        self.on_receive = on_receive

        try:
            self.logic_proc = subprocess.Popen(logic_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
            self.stdout_thread = threading.Thread(target=self.__listen_stdout)
            self.stderr_thread = threading.Thread(target=self.__listen_stderr)
            self.stdout_thread.start()
            self.stderr_thread.start()
        except:
            log.exception("Failed to start logic process. "
                          "Please check your logic_path and related permission.")
            raise JudgerIllegalState

        self.running = True
        log.info("Logic communication channel established")

    def close(self):
        log.info("Closing logic channel")
        self.running = False
        self.logic_proc.terminate()
        self.stderr_thread.join()
        self.stdout_thread.join()
        log.info("Logic channel is closed")

    def send(self, data: bytes):
        if not self.running:
            log.error("Logic channel is already closed")
        else:
            log.debug("Sending data to logic stdin: %s", data.decode("utf-8"))
            self.logic_proc.stdin.write(data)
            self.logic_proc.stdin.flush()

    def __listen_stdout(self):
        try:
            while self.running:
                pack_size = bytes2int(self.logic_proc.stdout.read(4))
                target = bytes2int(self.logic_proc.stdout.read(4))
                data = self.logic_proc.stdout.read(pack_size)
                log.debug("Received data from logic: %s", data.decode("utf-8"))
                self.on_receive(target, data)
        except:
            log.warning("Logic stdout disconnected unexpectedly", exc_info=True)

    def __listen_stderr(self):
        log.debug("Start capturing Logic stderr")
        try:
            logic_stderr_path = Path(self.output_dir) / "logic_stderr.txt"
            self.stderr_file = logic_stderr_path.open("w")
            log.debug("Logic stderr will also be logged into file: %s", logic_stderr_path)
        except IOError:
            log.exception("Cannot open logic stderr trace output file")
            raise JudgerIllegalState
        try:
            while self.running:
                line = self.logic_proc.stderr.readline()
                self.stderr_file.writelines([line])
                log.warning("Logic STDERR: %s", line)
        except:
            log.warning("Logic stderr disconnected unexpectedly", exc_info=True)
