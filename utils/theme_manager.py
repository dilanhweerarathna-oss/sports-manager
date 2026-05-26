from __future__ import annotations
from PySide6.QtCore import QObject, Signal


class ThemeManager(QObject):
    theme_changed = Signal(str)  # emits "dark" or "light"

    _instance: ThemeManager | None = None

    def __new__(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._mode = "dark"
        self._initialized = True

    @property
    def mode(self) -> str:
        return self._mode

    def apply(self, mode: str) -> None:
        self._mode = mode
        try:
            from qfluentwidgets import setTheme, Theme
            setTheme(Theme.DARK if mode == "dark" else Theme.LIGHT)
        except ImportError:
            pass
        self.theme_changed.emit(mode)

    def toggle(self) -> None:
        self.apply("light" if self._mode == "dark" else "dark")

    def is_dark(self) -> bool:
        return self._mode == "dark"


theme_manager = ThemeManager()
