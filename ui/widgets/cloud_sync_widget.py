"""Small clickable widget showing CloudSyncService status in the top bar."""
from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QFrame, QVBoxLayout, QPushButton,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer

from services.cloud_sync_service import CloudSyncService
from utils.logger import get_logger

logger = get_logger("cloud_sync_widget")


_STATE_STYLE = {
    "disabled":        ("◌",  "#9ca3af"),   # cloud not configured
    "ok":              ("✓",  "#27ae60"),   # green
    "syncing":         ("⟳",  "#2d5be3"),   # blue
    "transient_error": ("⚠",  "#f59e0b"),   # amber
    "paused":          ("✗",  "#e74c3c"),   # red
    "idle":            ("◌",  "#9ca3af"),   # gray (just started, no tick yet)
}

_STATE_TEXT = {
    "disabled":        "Cloud off",
    "ok":              "Synced",
    "syncing":         "Syncing…",
    "transient_error": "Offline",
    "paused":          "Sync error",
    "idle":            "Idle",
}


class CloudSyncStatusWidget(QFrame):
    """Compact pill in the top bar. Clicking opens a popover with details."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("cloudSyncPill")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)
        self._icon = QLabel("◌")
        self._icon.setStyleSheet("font-size: 13px;")
        self._text = QLabel("Cloud off")
        self._text.setStyleSheet("font-size: 11px; font-weight: 600;")
        layout.addWidget(self._icon)
        layout.addWidget(self._text)
        self.setStyleSheet(
            "QFrame#cloudSyncPill { border-radius: 12px; padding: 0 4px; }"
        )

        # Refresh every 2 seconds — cheap, reads a single DB row.
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._open_popover()
        super().mousePressEvent(ev)

    def _refresh(self) -> None:
        try:
            status = CloudSyncService.instance().get_status()
        except Exception as e:
            logger.warning(f"Status read failed: {e}")
            return
        state = status.get("state", "disabled")
        icon, color = _STATE_STYLE.get(state, _STATE_STYLE["disabled"])
        self._icon.setText(icon)
        self._icon.setStyleSheet(f"font-size: 13px; color: {color};")
        self._text.setText(_STATE_TEXT.get(state, state))
        self._text.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {color};")
        # Tooltip with details
        last_sync = status.get("last_sync_at") or "never"
        tooltip = f"State: {state}\nLast sync: {last_sync}"
        if status.get("last_error"):
            tooltip += f"\nLast error: {status['last_error']}"
        if status.get("consecutive_failures"):
            tooltip += f"\nConsecutive failures: {status['consecutive_failures']}"
        self.setToolTip(tooltip)

    def _open_popover(self) -> None:
        """Modal info dialog with Force-sync + log-path buttons."""
        try:
            status = CloudSyncService.instance().get_status()
        except Exception as e:
            QMessageBox.warning(self, "Cloud sync", f"Status unavailable: {e}")
            return

        from config import LOG_DIR
        log_path = LOG_DIR / "cloud_sync.log"
        state = status.get("state", "disabled")

        lines = [
            f"State: {state}",
            f"Last sync: {status.get('last_sync_at') or '—'}",
            f"Last push: {status.get('last_push_at') or '—'}",
            f"Last pull: {status.get('last_pull_at') or '—'}",
        ]
        if status.get("last_error"):
            lines += ["", f"Last error: {status['last_error']}",
                      f"At: {status.get('last_error_at')}"]
            lines.append(f"Consecutive failures: {status.get('consecutive_failures', 0)}")

        box = QMessageBox(self)
        box.setWindowTitle("Cloud sync")
        box.setText("Cloud sync status")
        box.setInformativeText("\n".join(lines))
        force = box.addButton("Force sync now", QMessageBox.ButtonRole.AcceptRole)
        open_log = box.addButton("Open log folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()

        clicked = box.clickedButton()
        if clicked is force:
            try:
                CloudSyncService.instance().force_sync_now()
                logger.info("Force sync triggered from widget")
            except Exception as e:
                QMessageBox.warning(self, "Cloud sync", f"Failed: {e}")
        elif clicked is open_log:
            self._open_log_folder(log_path)

    def _open_log_folder(self, log_path) -> None:
        import os
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        target = str(log_path if log_path.exists() else log_path.parent)
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))
        except Exception as e:
            QMessageBox.information(self, "Log folder", f"Open this folder:\n{target}\n\n{e}")
