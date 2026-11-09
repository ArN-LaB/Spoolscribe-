"""B18/A4: the finite opening of the « Accueil rapide » panel, transposed from the Companion.

The same SVG logo appears centred in the panel, pulses once, then shrinks and settles in the
header slot (top left, next to the title) while the title and the content fade in. One
``QVariantAnimation`` of 750 ms drives every phase; nothing loops and nothing remains at rest:
when it ends, or as soon as the panel is hidden, resized past it or closed, the final state is
applied, the overlay is removed and the opacity effects are dropped. The logo in the header is a
static SVG render with no timer (unlike ``SpinningLogo``).

Reduced motion (system accessibility setting, read only) gives the final state immediately.
``SPOOLSCRIBE_REDUCE_MOTION=1`` forces that branch for tests; it is not a user setting.
"""
import math
import os
import sys

from PySide6.QtCore import QAbstractAnimation, QEvent, QObject, QPoint, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

try:
    from PySide6.QtSvg import QSvgRenderer
except Exception:  # pragma: no cover - QtSvg is part of the supported builds
    QSvgRenderer = None

# Companion reference (B18/E056): lib/core/opening.dart.
DURATION_MS = 750
LOGO_START = 112
LOGO_END = 36
PULSE_INTERVAL = (0.0, 0.32)
PULSE_MAX = 1.04
MOVE_INTERVAL = (0.2, 0.86)
REVEAL_INTERVAL = (0.66, 1.0)
REDUCE_MOTION_ENV = 'SPOOLSCRIBE_REDUCE_MOTION'


def _segment(t, interval):
    start, end = interval
    return 0.0 if t <= start else 1.0 if t >= end else (t - start) / (end - start)


def ease_in_out_cubic(x):
    return 4 * x * x * x if x < 0.5 else 1 - pow(-2 * x + 2, 3) / 2


def _macos_reduce_motion():
    """NSWorkspace.accessibilityDisplayShouldReduceMotion, read through the Objective-C runtime."""
    import ctypes
    objc = ctypes.cdll.LoadLibrary('/usr/lib/libobjc.A.dylib')
    ctypes.cdll.LoadLibrary('/System/Library/Frameworks/AppKit.framework/AppKit')
    objc.objc_getClass.restype = ctypes.c_void_p; objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p; objc.sel_registerName.argtypes = [ctypes.c_char_p]
    address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    send_id = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
    send_bool = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(address)
    workspace_class = objc.objc_getClass(b'NSWorkspace')
    if not workspace_class:
        return False
    workspace = send_id(workspace_class, objc.sel_registerName(b'sharedWorkspace'))
    return bool(workspace) and bool(send_bool(workspace, objc.sel_registerName(b'accessibilityDisplayShouldReduceMotion')))


def _windows_reduce_motion():
    import ctypes
    enabled = ctypes.c_int(1)
    SPI_GETCLIENTAREAANIMATION = 0x1042
    if not ctypes.windll.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0):
        return False
    return not enabled.value


def reduced_motion():
    """True when animations should be skipped. Never writes any preference; unknown means animate."""
    forced = os.environ.get(REDUCE_MOTION_ENV)
    if forced is not None:
        return forced.strip().lower() not in ('', '0', 'false', 'no')
    try:
        if sys.platform == 'darwin':
            return _macos_reduce_motion()
        if sys.platform == 'win32':
            return _windows_reduce_motion()
    except Exception:
        return False
    return False


def logo_renderer(path):
    """A valid static SVG renderer for ``path``, or None (missing file, QtSvg absent, unreadable SVG)."""
    if not path or QSvgRenderer is None:
        return None
    renderer = QSvgRenderer(path)
    return renderer if renderer.isValid() else None


class StaticLogo(QWidget):
    """The header logo: a single SVG render, no timer, no animation."""

    def __init__(self, renderer, size=LOGO_END, parent=None):
        super().__init__(parent)
        self.renderer = renderer
        self._painted = True
        self.setObjectName('welcomeLogo')
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def set_painted(self, painted):
        # The slot keeps its size in the layout while the moving copy is drawn above it.
        if painted != self._painted:
            self._painted = painted
            self.update()

    def is_painted(self):
        return self._painted

    def paintEvent(self, event):
        if not self._painted:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.renderer.render(painter, QRectF(self.rect()))


class _OpeningOverlay(QWidget):
    """Transparent layer above the panel drawing the moving logo; ignores the mouse."""

    def __init__(self, dialog, renderer):
        super().__init__(dialog)
        self.setObjectName('welcomeOpeningOverlay')
        self.renderer = renderer
        self.logo_rect = QRectF()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setGeometry(dialog.rect())

    def set_logo_rect(self, rect):
        previous, self.logo_rect = self.logo_rect, rect
        self.update(previous.united(rect).toAlignedRect().adjusted(-2, -2, 2, 2))

    def paintEvent(self, event):
        if self.logo_rect.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.renderer.render(painter, self.logo_rect)


class WelcomeOpening(QObject):
    """Plays the opening once on ``dialog``, or applies the final state at once when ``animate`` is false."""

    settled = Signal()

    def __init__(self, dialog, logo, reveal, *, animate):
        super().__init__(dialog)
        self.dialog, self.logo = dialog, logo
        self.done = False
        self.played = False
        self.progress = 1.0
        self._effects = []
        self._overlay = None
        self._animation = None
        if not animate or logo is None:
            return
        self.progress = 0.0
        for widget in reveal:
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)
            self._effects.append(widget)
        logo.set_painted(False)
        self._overlay = _OpeningOverlay(dialog, logo.renderer)
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(DURATION_MS)
        self._animation.valueChanged.connect(self._frame)
        self._animation.finished.connect(self.finish)
        dialog.installEventFilter(self)
        dialog.finished.connect(self.finish)

    def is_animating(self):
        return self._animation is not None and self._animation.state() == QAbstractAnimation.Running

    def start(self):
        """Call once the panel is shown and laid out, so the header slot has its real position."""
        if self._animation is None:
            self.finish()
            return
        self.played = True
        self._overlay.raise_()
        self._overlay.show()
        self._frame(0.0)
        self._animation.start()

    def logo_geometry(self, t):
        """Logo rectangle in panel coordinates at progress ``t`` (0 → 1)."""
        width, height = self.dialog.width(), self.dialog.height()
        slot = QRectF(self.logo.mapTo(self.dialog, QPoint(0, 0)), self.logo.size())
        # A small panel never gets a logo larger than ~40 % of its short side.
        start = min(float(LOGO_START), 0.4 * min(width, height))
        pulse = 1 + (PULSE_MAX - 1) * math.sin(math.pi * _segment(t, PULSE_INTERVAL))
        move = ease_in_out_cubic(_segment(t, MOVE_INTERVAL))
        size = start * pulse + (slot.width() - start * pulse) * move
        cx = width / 2 + (slot.center().x() - width / 2) * move
        cy = height / 2 + (slot.center().y() - height / 2) * move
        return QRectF(cx - size / 2, cy - size / 2, size, size)

    @staticmethod
    def reveal_opacity(t):
        r = _segment(t, REVEAL_INTERVAL)
        return 1 - (1 - r) * (1 - r)  # ease-out

    def _frame(self, value):
        if self.done:
            return
        self.progress = t = float(value)
        self._overlay.set_logo_rect(self.logo_geometry(t))
        opacity = self.reveal_opacity(t)
        for widget in self._effects:
            effect = widget.graphicsEffect()
            if effect is not None:
                effect.setOpacity(opacity)

    def eventFilter(self, obj, event):
        if obj is self.dialog and not self.done:
            kind = event.type()
            if kind == QEvent.Resize and self._overlay is not None:
                self._overlay.setGeometry(self.dialog.rect())
                self._frame(self.progress)
            elif kind == QEvent.Hide:
                self.finish()
        return False

    def finish(self, *_):
        """Final state: static logo in the header, content fully visible, nothing left running."""
        if self.done:
            return
        self.done = True
        self.progress = 1.0
        if self._animation is not None:
            self._animation.valueChanged.disconnect(self._frame)
            if self._animation.state() != QAbstractAnimation.Stopped:
                self._animation.stop()
            self._animation.deleteLater()
            self._animation = None
            self.dialog.removeEventFilter(self)
        for widget in self._effects:
            try:
                widget.setGraphicsEffect(None)
            except RuntimeError:  # widget already destroyed with the panel
                pass
        self._effects = []
        if self._overlay is not None:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        if self.logo is not None:
            try:
                self.logo.set_painted(True)
            except RuntimeError:
                pass
        self.settled.emit()
