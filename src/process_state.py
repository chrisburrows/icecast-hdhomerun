from enum import Enum


class ProcessState(Enum):
    STARTED = 1
    STOPPED = 2
    FINISHED = 3
    ERROR = 4