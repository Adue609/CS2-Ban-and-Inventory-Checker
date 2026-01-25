import logging
import os
from typing import Optional

# Internal flag for debug state
_DEBUG_ENABLED = os.environ.get("LOG_DEBUG", "0") in ("1", "true", "True", "yes", "on")


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once for the application."""
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setLevel(level)
            h.setFormatter(formatter)

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