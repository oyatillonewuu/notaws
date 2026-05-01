from enum import StrEnum, auto


class ResultStatus(StrEnum):
    success = auto()
    error = auto()
    warning = auto()
