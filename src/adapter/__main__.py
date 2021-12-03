import argparse
import socket
import subprocess
from queue import Queue
from threading import Thread, Condition, current_thread
from typing import Callable

parser = argparse.ArgumentParser(prog="python -m adapter")
parser.add_argument("judger_ip", type=str, help="IP address of local judger server")
parser.add_argument("judger_port", type=int, help="Port of local judger server")
parser.add_argument("ai_path", type=str, help="Path of to-be-adapted AI program")
args = parser.parse_args()

judger_ip = args.judger_ip
judger_port = args.judger_port
ai_path = args.ai_path

# Wait for any of the listening thread is broken
condition = Condition()

# Data buffer
to_ai_buffer = Queue()
from_ai_buffer = Queue()


def infinity_loop(task: Callable) -> Callable:
    def loop():
        try:
            while True:
                task()
        finally:
            print("{} is broken".format(current_thread().name))
            condition.notify_all()

    return loop


# Launch AI
ai_process = subprocess.Popen(ai_path, bufsize=0, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
ai_stdin_thread = Thread(target=infinity_loop(lambda: ai_process.stdin.write(to_ai_buffer.get())), name="AI stdin")
ai_stdin_thread.daemon = True
ai_stdout_thread = Thread(target=infinity_loop(lambda: from_ai_buffer.put(ai_process.stdout.read(1))), name="AI stdout")
ai_stdout_thread.daemon = True

# Connect to local judger
judger_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
judger_socket.connect((judger_ip, judger_port))
judger_recv_thread = Thread(target=infinity_loop(lambda: to_ai_buffer.put(judger_socket.recv(1))),
                            name="Judger socket recv")
judger_recv_thread.daemon = True
judger_send_thread = Thread(target=infinity_loop(lambda: judger_socket.send(from_ai_buffer.get())),
                            name="Judger socket send")
judger_recv_thread.daemon = True

# Wait for broken channel
condition.wait()
exit_code = ai_process.poll()
if exit_code is not None:
    print("AI process exit".format(exit_code))
