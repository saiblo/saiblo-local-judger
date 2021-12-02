def bytes2int(data: bytes) -> int:
    return int.from_bytes(data, byteorder="big")


def int2bytes(x: int) -> bytes:
    return int.to_bytes(x, byteorder="big")
