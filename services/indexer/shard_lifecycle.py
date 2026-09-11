from enum import Enum


class ShardLifecycleState(str, Enum):
    NEW = "new"
    LOADING = "loading"
    PERSISTING = "persisting"
    READY = "ready"
    FAILED = "failed"