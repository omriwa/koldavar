# modules/logger.py
import logging
import traceback
from datetime import datetime
from pathlib import Path

class KoldavarLogger:
    """
    Centralized, structured application logger for Koldavar.
    Supports event IDs, severity levels, and error traces.
    """

    def __init__(self, name="Koldavar", log_dir="logs", level=logging.INFO):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"{name.lower()}.log"
        self.logger = logging.getLogger(name)

        if not self.logger.handlers:
            formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(event_id)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

            self.logger.setLevel(level)
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def _log(self, level, event_id, message, exc: Exception = None):
        """
        Internal structured log function.
        Adds event_id and trace if applicable.
        """
        extra = {"event_id": event_id}
        if exc:
            trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            message = f"{message}\nTRACE:\n{trace}"

        self.logger.log(level, message, extra=extra)

    # Public API methods:
    def info(self, event_id, message):
        self._log(logging.INFO, event_id, message)

    def warning(self, event_id, message):
        self._log(logging.WARNING, event_id, message)

    def error(self, event_id, message, exc=None):
        self._log(logging.ERROR, event_id, message, exc)

    def critical(self, event_id, message, exc=None):
        self._log(logging.CRITICAL, event_id, message, exc)
