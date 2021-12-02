import socket
import socketserver
import subprocess
import threading
from logging import Logger
from pathlib import Path
from typing import Callable, TextIO

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
            log.exception("AI Channel is closed due to exception")
            self.on_closed()

    def send(self, data: bytes) -> None:
        log.debug("Sending data to %s: %s", self.client_address, data.decode("utf-8"))
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except socket.error:
            log.exception("AI Channel is closed due to exception")
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
        self.running = True
        self.output_dir = output_dir
        self.on_receive = on_receive

        self.logic_proc = subprocess.Popen(logic_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
        self.stdout_thread = threading.Thread(target=self.__listen_stdout)
        self.stderr_thread = threading.Thread(target=self.__listen_stderr)
        self.stdout_thread.start()
        self.stderr_thread.start()

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
            log.warning("Logic stdout disconnected due to exception", exc_info=True)

    def __listen_stderr(self):
        log.debug("Start capturing Logic stderr")
        self.stderr_file = (Path(self.output_dir) / "logic_stderr.txt").open("w")
        try:
            while self.running:
                line = self.logic_proc.stderr.readline()
                self.stderr_file.writelines([line])
                log.warning("Logic STDERR: %s", line)
        except:
            log.warning("Logic stderr disconnected due to exception", exc_info=True)
