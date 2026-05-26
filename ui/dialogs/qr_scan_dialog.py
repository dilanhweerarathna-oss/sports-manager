"""
Desktop QR scanner for membership cards.

Opens the laptop's webcam in a modal, decodes any membership-card QR
(`SM1.<admission_no>.<hmac8>`), HMAC-verifies the signature against the
local card secret, and exposes the validated `admission_no` to the caller
via `scanned_admission_no`. The Attendance page funnels the result back
into its existing `_on_scan_enter` flow so all downstream UX (row flash,
counts, etc.) is reused.

Non-SM1 QR codes are ignored with a throttled hint — the camera keeps
running so the user doesn't get the dialog closed on an irrelevant code.
"""
from __future__ import annotations

import time
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import (
    QCamera,
    QMediaCaptureSession,
    QMediaDevices,
    QVideoFrame,
    QVideoSink,
)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

import cv2

from services.membership_card_service import MembershipCardService
from utils.logger import get_logger

logger = get_logger("qr_scan_dialog")

_DECODE_INTERVAL_MS = 150          # throttle: decode every ~150 ms (≈6/s)
_NON_CARD_HINT_MS = 1500           # how long the "Not a membership card" hint lingers


class QrScanDialog(QDialog):
    """Modal camera dialog. On a valid, HMAC-verified card scan, accepts
    with `scanned_admission_no` set to the validated admission number."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scanned_admission_no: Optional[str] = None

        self._card_service = MembershipCardService()
        self._detector = cv2.QRCodeDetector()
        self._last_decode_at = 0.0
        self._hint_clear_at = 0.0

        self._camera: Optional[QCamera] = None
        self._session: Optional[QMediaCaptureSession] = None
        self._video_widget: Optional[QVideoWidget] = None
        self._video_sink: Optional[QVideoSink] = None

        self.setWindowTitle("Scan Membership Card")
        self.setModal(True)
        self.resize(640, 540)
        self._setup_ui()
        self._start_camera()

        # Periodic timer to clear stale "ignore" hints so the screen doesn't
        # get stuck on an old message after the user moves the card away.
        self._hint_timer = QTimer(self)
        self._hint_timer.setInterval(250)
        self._hint_timer.timeout.connect(self._maybe_clear_hint)
        self._hint_timer.start()

    # ── UI ──────────────────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        title = QLabel("Point camera at a student's membership card")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        root.addWidget(title)

        self._video_widget = QVideoWidget(self)
        self._video_widget.setMinimumSize(560, 380)
        self._video_widget.setStyleSheet("background:#000; border-radius:6px;")
        root.addWidget(self._video_widget, stretch=1)

        self._hint = QLabel(" ")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet("color:#6b7280; font-size:12px; min-height:18px;")
        root.addWidget(self._hint)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    # ── Camera lifecycle ────────────────────────────────────────────────────
    def _start_camera(self) -> None:
        devices = QMediaDevices.videoInputs()
        if not devices:
            self._set_hint("No camera detected. Plug one in and reopen.", error=True)
            return

        self._camera = QCamera(devices[0], self)
        self._session = QMediaCaptureSession(self)
        self._session.setCamera(self._camera)
        self._session.setVideoOutput(self._video_widget)

        # A second sink runs alongside the display sink to give us raw frames
        # for decoding without disturbing the live preview.
        self._video_sink = QVideoSink(self)
        self._session.setVideoSink(self._video_sink)
        self._video_sink.videoFrameChanged.connect(self._on_frame)

        try:
            self._camera.start()
        except Exception as e:
            logger.exception("Camera start failed")
            self._set_hint(f"Camera error: {e}", error=True)
            return

        if not self._camera.isActive():
            # On Windows, start() can return without raising but still fail
            # silently (driver / privacy permission). Surface that.
            self._set_hint(
                "Could not start camera. Check Windows camera permissions.",
                error=True,
            )

    def _stop_camera(self) -> None:
        try:
            if self._video_sink is not None:
                try:
                    self._video_sink.videoFrameChanged.disconnect(self._on_frame)
                except (RuntimeError, TypeError):
                    pass
            if self._camera is not None:
                self._camera.stop()
        except Exception:
            logger.debug("Camera teardown raised (ignored)", exc_info=True)
        finally:
            self._video_sink = None
            self._camera = None
            self._session = None

    # ── Frame handling ──────────────────────────────────────────────────────
    def _on_frame(self, frame: QVideoFrame) -> None:
        # Throttle — webcams push 30 fps and decoding is the expensive part.
        now = time.monotonic()
        if (now - self._last_decode_at) * 1000 < _DECODE_INTERVAL_MS:
            return
        self._last_decode_at = now

        if not frame.isValid():
            return

        img = frame.toImage()
        if img.isNull():
            return

        gray = _qimage_to_grayscale_array(img)
        if gray is None:
            return

        try:
            text, _pts, _ = self._detector.detectAndDecode(gray)
        except cv2.error:
            return

        if not text:
            return

        self._handle_decoded(text)

    def _handle_decoded(self, text: str) -> None:
        raw = text.strip()
        if not raw.startswith("SM1."):
            self._set_hint("Not a membership card", error=True, transient=True)
            return

        admission_no = self._card_service.verify_token(raw)
        if admission_no is None:
            self._set_hint("Invalid card signature", error=True, transient=True)
            return

        # Valid card. Stop the camera before accepting so the device is
        # released even if the parent's slot takes a moment to run.
        self.scanned_admission_no = admission_no
        self._stop_camera()
        self.accept()

    # ── Hint label helpers ──────────────────────────────────────────────────
    def _set_hint(self, text: str, *, error: bool = False, transient: bool = False) -> None:
        colour = "#dc2626" if error else "#6b7280"
        self._hint.setStyleSheet(
            f"color:{colour}; font-size:12px; min-height:18px;"
        )
        self._hint.setText(text)
        if transient:
            self._hint_clear_at = time.monotonic() + (_NON_CARD_HINT_MS / 1000)
        else:
            self._hint_clear_at = 0.0

    def _maybe_clear_hint(self) -> None:
        if self._hint_clear_at and time.monotonic() >= self._hint_clear_at:
            self._hint.setText(" ")
            self._hint_clear_at = 0.0

    # ── Lifecycle hooks ─────────────────────────────────────────────────────
    def reject(self) -> None:
        self._stop_camera()
        super().reject()

    def closeEvent(self, event) -> None:
        self._stop_camera()
        super().closeEvent(event)


# ─── Helpers ────────────────────────────────────────────────────────────────
def _qimage_to_grayscale_array(img: QImage) -> Optional[np.ndarray]:
    """Convert a QImage to a contiguous grayscale numpy array suitable for
    cv2. Returns None on unsupported pixel formats."""
    if img.isNull():
        return None
    img = img.convertToFormat(QImage.Format.Format_Grayscale8)
    if img.isNull():
        return None
    width = img.width()
    height = img.height()
    if width <= 0 or height <= 0:
        return None
    # QImage uses padded scanlines; bytesPerLine() may exceed width. Slice
    # off the padding when constructing the array view.
    bpl = img.bytesPerLine()
    buf = img.constBits().tobytes()
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((height, bpl))[:, :width]
    return np.ascontiguousarray(arr)
