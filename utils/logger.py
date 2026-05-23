import logging
import sys
from logging.handlers import RotatingFileHandler
from config import LOG_DIR, LOG_LEVEL

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_app_handler = RotatingFileHandler(
    LOG_DIR / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_app_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))

_error_handler = RotatingFileHandler(
    LOG_DIR / "error.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_error_handler.setLevel(logging.ERROR)
_error_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))

_root = logging.getLogger("sports_manager")
_root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
_root.addHandler(_app_handler)
_root.addHandler(_error_handler)
_root.addHandler(_console_handler)
_root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return _root.getChild(name)


def install_global_exception_hook() -> None:
    """Catch all unhandled exceptions and write them to error.log."""
    _err_logger = get_logger("unhandled")

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        _err_logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _hook
