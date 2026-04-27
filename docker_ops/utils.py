import io
from typing import IO


def str_to_file_obj(string: str) -> IO:
    return io.BytesIO(bytes(string, "utf-8"))
