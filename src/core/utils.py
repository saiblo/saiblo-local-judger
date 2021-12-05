def bytes2int(data: bytes) -> int:
    return int.from_bytes(data, byteorder="big", signed=True)


def int2bytes(x: int) -> bytes:
    return int.to_bytes(x, length=4, byteorder="big", signed=True)
