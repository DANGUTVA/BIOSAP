"""Basic scheduler placeholder for periodic refresh."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class BasicScheduler:
    """In-process scheduler state for MVP."""

    interval_seconds: int = 300
    _next_run: datetime | None = None

    def should_run(self) -> bool:
        now = datetime.utcnow()
        if self._next_run is None:
            self._next_run = now + timedelta(seconds=self.interval_seconds)
            return True
        if now >= self._next_run:
            self._next_run = now + timedelta(seconds=self.interval_seconds)
            return True
        return False
