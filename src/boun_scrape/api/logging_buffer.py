"""In-memory circular log buffer and logging handler for API observability."""

from collections import deque
from datetime import datetime, timezone
import logging
from threading import Lock
from typing import Any

from boun_scrape.domain.dto import LogEntryDTO


class LogBuffer:
    """Thread-safe circular in-memory buffer storing recent log entries."""

    def __init__(self, capacity: int = 1000) -> None:
        self.capacity = capacity
        self._records: deque[LogEntryDTO] = deque(maxlen=capacity)
        self._lock = Lock()

    def add(self, level: str, name: str, message: str, timestamp: str | None = None) -> LogEntryDTO:
        """Append a new log entry to the buffer."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        entry = LogEntryDTO(
            timestamp=ts,
            level=level.upper(),
            name=name,
            message=message,
        )
        with self._lock:
            self._records.append(entry)
        return entry

    def get_logs(self, limit: int = 100, level: str | None = None) -> list[LogEntryDTO]:
        """Retrieve recent log records, optionally filtered by minimum log level."""
        with self._lock:
            entries = list(self._records)

        if level:
            target_lvl = level.upper().strip()
            entries = [e for e in entries if e.level == target_lvl]

        return entries[-limit:]

    def clear(self) -> None:
        """Clear all buffered log records."""
        with self._lock:
            self._records.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)


class BufferLoggingHandler(logging.Handler):
    """Logging handler that writes formatted log records into a LogBuffer instance."""

    def __init__(self, buffer: LogBuffer) -> None:
        super().__init__()
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.buffer.add(
                level=record.levelname,
                name=record.name,
                message=msg,
            )
        except Exception:
            self.handleError(record)


# Global singleton instance
_GLOBAL_LOG_BUFFER = LogBuffer(capacity=1000)


def get_global_log_buffer() -> LogBuffer:
    """Access the global application log buffer."""
    return _GLOBAL_LOG_BUFFER


def setup_api_logging(logger_name: str = "boun_scrape") -> LogBuffer:
    """Attach the buffer logging handler to the root or specified logger."""
    buf = get_global_log_buffer()
    logger = logging.getLogger(logger_name)
    handler = BufferLoggingHandler(buf)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return buf
