from enum import StrEnum, auto


class Status(StrEnum):
    success = auto()
    failed = auto()
    warning = auto()
