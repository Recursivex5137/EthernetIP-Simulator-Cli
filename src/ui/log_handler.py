"""Qt-compatible logging handler for UI display"""

import logging
import time
from datetime import datetime
from PySide6.QtCore import QObject, Signal


class QtLogHandler(logging.Handler, QObject):
    """
    Custom log handler that emits Qt signals for UI display.

    This handler is thread-safe and can be used to capture log messages
    from any thread and display them in a Qt UI component.

    Rate-limited to prevent UI flooding: when signals exceed MAX_RATE/sec,
    INFO and DEBUG messages are dropped. ERROR and WARNING always pass.
    """

    MAX_RATE = 50  # Max signals per second before throttling INFO/DEBUG

    # Signal emits: (timestamp, level, message)
    log_signal = Signal(str, str, str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self._window_start = time.perf_counter()
        self._msg_count = 0
        self._dropped = 0

    def emit(self, record: logging.LogRecord):
        """
        Emit a log record as a Qt signal.

        Args:
            record: The logging.LogRecord to emit
        """
        try:
            now = time.perf_counter()
            self._msg_count += 1

            # Reset the rate window every second
            if now - self._window_start >= 1.0:
                self._msg_count = 1
                self._window_start = now

            # Throttle: drop INFO/DEBUG when rate exceeds MAX_RATE
            if self._msg_count > self.MAX_RATE and record.levelno < logging.WARNING:
                self._dropped += 1
                return

            # Emit a summary of dropped messages before resuming
            if self._dropped > 0:
                dropped = self._dropped
                self._dropped = 0
                summary_ts = self._format_time(record)
                self.log_signal.emit(
                    summary_ts, "WARNING",
                    f"[Log throttled: {dropped} messages dropped due to high rate]"
                )

            # Format timestamp as HH:MM:SS.mmm
            timestamp = self._format_time(record)

            # Get level name
            level = record.levelname

            # Get the formatted message
            message = record.getMessage()

            # Emit the signal (thread-safe due to Qt's queued connection)
            self.log_signal.emit(timestamp, level, message)

        except Exception:
            # If anything goes wrong, use the default error handling
            self.handleError(record)

    def _format_time(self, record: logging.LogRecord) -> str:
        """
        Format the log record timestamp.

        Args:
            record: The logging.LogRecord

        Returns:
            Formatted timestamp string (HH:MM:SS.mmm)
        """
        dt = datetime.fromtimestamp(record.created)
        return dt.strftime('%H:%M:%S.%f')[:-3]  # Remove last 3 microsecond digits
