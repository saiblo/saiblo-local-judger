#!python

import sys

while True:
    read_buffer = sys.stdin.buffer
    data_len = int.from_bytes(read_buffer.read(4), byteorder='big', signed=True)
    print(data_len, file=sys.stderr, flush=True)
    data = read_buffer.read(data_len)
    print(data, file=sys.stderr, flush=True)
