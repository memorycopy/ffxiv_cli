"""Event system for handling time-based callbacks in XIV gameplay mechanics."""

from typing import Callable, Any, Tuple, Dict


class Task:
    """An event in the game that occurs at a specific time."""

    def __init__(self, time: float, callback: Callable, args: Tuple[Any, ...] = (), kwargs: Dict[str, Any] = None):
        self.time = time
        self.callback = callback
        self.args = args
        self.kwargs = kwargs or {}

    def __lt__(self, other):
        return self.time < other.time
        
    def execute(self):
        """Execute the callback function with the provided args and kwargs."""
        return self.callback(*self.args, **self.kwargs)
