import argparse
import asyncio
from pathlib import Path

parser = argparse.ArgumentParser(prog="python -m adapter")
parser.add_argument("judger_ip", type=str, help="IP address of local judger server")
parser.add_argument("judger_port", type=int, help="Port of local judger server")
parser.add_argument("ai_path", type=str, help="Path of to-be-adapted AI program")
args = parser.parse_args()

judger_ip = args.judger_ip
judger_port = args.judger_port
ai_path = args.ai_path


async def bridge_stream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    while True:
        data = await reader.readexactly(1)
        writer.write(data)
        await writer.drain()


async def wait_process(proc: asyncio.subprocess.Process):
    return_code = await proc.wait()
    print("AI process exited: ", return_code)


async def run():
    ai_proc = await asyncio.create_subprocess_shell(
        str(Path.cwd() / ai_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=None,
    )
    print("Launched AI process")
    (socket_reader, socket_writer) = await asyncio.open_connection(judger_ip, judger_port)
    print("Connected to local judger")
    await asyncio.gather(
        bridge_stream(ai_proc.stdout, socket_writer),
        bridge_stream(socket_reader, ai_proc.stdin),
        wait_process(ai_proc),
        return_exceptions=True
    )


def main():
    asyncio.run(run())
