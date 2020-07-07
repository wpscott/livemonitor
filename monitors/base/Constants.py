from enum import Enum


class LogLevel(Enum):
    Error = 0
    Stop = 1
    Info = 10
    Check = 11
    Start = 12
    Success = 20
