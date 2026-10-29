"""Drains a TaskQueue, with a retry budget per task."""

import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class Worker:
    """Pulls tasks off a queue and runs registered handlers."""

    def __init__(self, queue):
        self.queue = queue
        self.handlers = {}
        self.failed = []

    def register(self, name, fn):
        """Bind a handler function to a task name."""
        self.handlers[name] = fn

    def run_once(self):
        """Run a single task. Returns True if a task was processed."""
        task = self.queue.pop()
        if task is None:
            return False
        handler = self.handlers.get(task.name)
        if handler is None:
            logger.warning("no handler for %s", task.name)
            self.failed.append(task)
            return True
        for attempt in range(MAX_RETRIES):
            try:
                handler(task.payload)
                return True
            except (ValueError, KeyError) as exc:
                logger.warning("%s failed on attempt %d: %s", task.name, attempt + 1, exc)
        self.failed.append(task)
        return True

    def drain(self):
        """Run until the queue is empty. Returns the number of tasks run."""
        count = 0
        while self.run_once():
            count += 1
        return count
