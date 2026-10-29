"""A minimal in-memory priority task queue."""

import heapq
import itertools
from dataclasses import dataclass, field


@dataclass(order=True)
class Task:
    """One unit of work. Lower priority value runs first."""

    priority: int
    seq: int
    name: str = field(compare=False)
    payload: dict = field(compare=False, default_factory=dict)


class TaskQueue:
    """A priority queue with stable ordering for equal priorities."""

    def __init__(self):
        self._heap = []
        self._counter = itertools.count()

    def push(self, name, priority=5, payload=None):
        """Add a task. Returns the task's sequence number."""
        seq = next(self._counter)
        heapq.heappush(self._heap, Task(priority, seq, name, payload or {}))
        return seq

    def pop(self):
        """Remove and return the highest-priority task, or None if empty."""
        if not self._heap:
            return None
        return heapq.heappop(self._heap)

    def __len__(self):
        return len(self._heap)
