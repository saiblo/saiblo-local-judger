import argparse
import asyncio

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


async def main():
    ai_proc = await asyncio.create_subprocess_shell(
        ai_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    (socket_reader, socket_writer) = await asyncio.open_connection(judger_ip, judger_port)
    await asyncio.gather(
        asyncio.create_task(bridge_stream(ai_proc.stdout, socket_writer)),
        asyncio.create_task(bridge_stream(socket_reader, ai_proc.stdin)),
        return_exceptions=True
    )


asyncio.run(main())
