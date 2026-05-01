import logging
import os
import threading
from typing import Optional, Dict
from pathlib import Path

# Internal flag for debug state
_DEBUG_ENABLED = os.environ.get("LOG_DEBUG", "0") in ("1", "true", "True", "yes", "on")


class _PerThreadFileHandler(logging.Handler):
    """Write logs to one file per thread for easier runtime tracing."""

    def __init__(self, logs_dir: str = "logs/threads", level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self._base_dir = Path(logs_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._handlers: Dict[str, logging.FileHandler] = {}

    @staticmethod
    def _sanitize(name: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in name)
        return safe or "unknown-thread"

    def _get_handler_for_current_thread(self) -> logging.FileHandler:
        thread_name = self._sanitize(threading.current_thread().name)
        handler = self._handlers.get(thread_name)
        if handler is None:
            path = self._base_dir / f"{thread_name}.log"
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.setLevel(self.level)
            if self.formatter:
                handler.setFormatter(self.formatter)
            self._handlers[thread_name] = handler
        return handler

    def emit(self, record: logging.LogRecord) -> None:
        try:
            handler = self._get_handler_for_current_thread()
            handler.emit(record)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        for handler in self._handlers.values():
            try:
                handler.close()
            except Exception:
                pass
        self._handlers.clear()
        super().close()


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once for the application."""
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    per_thread_handler = _PerThreadFileHandler(level=level)
    per_thread_handler.setFormatter(formatter)

    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
        root.addHandler(per_thread_handler)
    else:
        for h in root.handlers:
            h.setLevel(level)
            h.setFormatter(formatter)
        if not any(isinstance(h, _PerThreadFileHandler) for h in root.handlers):
            root.addHandler(per_thread_handler)

    root.setLevel(level)


def _apply_debug_state(enabled: bool) -> None:
    """Apply the debug enabled/disabled state to existing handlers and root logger."""
    root = logging.getLogger()
    level = logging.DEBUG if enabled else logging.INFO
    root.setLevel(level)
    for h in root.handlers:
        h.setLevel(level)


def set_debug(enabled: bool) -> None:
    """
    Toggle debug logging on or off at runtime.

    - enabled=True: set root and handlers to DEBUG.
    - enabled=False: set root and handlers to INFO.
    """
    global _DEBUG_ENABLED
    _DEBUG_ENABLED = bool(enabled)
    _apply_debug_state(_DEBUG_ENABLED)


def is_debug_enabled() -> bool:
    """Return current debug toggle state."""
    return _DEBUG_ENABLED


def get_logger(name: Optional[str] = None, level: Optional[int] = None) -> logging.Logger:
    """
    Return a configured logger. If logging hasn't been configured yet this
    will perform a default configuration. Honors the LOG_DEBUG env var.
    """
    # Ensure a basic configuration exists
    if not logging.getLogger().handlers:
        # default level depends on initial debug flag
        configure_logging(logging.DEBUG if _DEBUG_ENABLED else logging.INFO)
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger