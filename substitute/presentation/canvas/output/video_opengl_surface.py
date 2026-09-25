#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Compose libmpv frames inside Qt's normal OpenGL widget stack."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QTimer, Qt, Signal, Slot
from PySide6.QtGui import QContextMenuEvent, QOpenGLContext, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget

from substitute.application.ports.video import VideoOpenGLPlayerPort, VideoPlayerPort

_GL_COLOR_BUFFER_BIT = 0x00004000
_GL_SCISSOR_TEST = 0x0C11


class VideoOpenGLSurface(QOpenGLWidget):
    """Render video as Qt content so chrome and pointer input remain authoritative."""

    renderingReady = Signal()
    surfaceResized = Signal()
    contextMenuRequested = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        clear_framebuffer: Callable[[], None] | None = None,
    ) -> None:
        """Create an initially unbound transparent OpenGL surface."""

        super().__init__(parent)
        self.setObjectName("outputVideoRenderSurface")
        surface_format = QSurfaceFormat(self.format())
        surface_format.setAlphaBufferSize(8)
        self.setFormat(surface_format)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent; border: none;")
        self._clear_framebuffer = (
            clear_transparent_opengl_framebuffer
            if clear_framebuffer is None
            else clear_framebuffer
        )
        self._player: VideoOpenGLPlayerPort | None = None
        self._renderer_initialized = False
        self._renderer_context: QOpenGLContext | None = None
        self._observed_context: QOpenGLContext | None = None
        self._render_poll = QTimer(self)
        self._render_poll.setInterval(16)
        self._render_poll.timeout.connect(self._poll_frame)

    def bind_player(self, player: VideoPlayerPort) -> None:
        """Bind a render-capable player when the controller creates it."""

        if not isinstance(player, VideoOpenGLPlayerPort):
            return
        if player is self._player and self._renderer_initialized:
            return
        self.release_player()
        self._player = player
        if self.context() is not None and self.isValid():
            self.makeCurrent()
            try:
                self._initialize_renderer()
            finally:
                self.doneCurrent()

    @property
    def rendering_ready(self) -> bool:
        """Return whether Qt has created the surface's usable OpenGL context."""

        return self.context() is not None and self.isValid()

    def release_player(self) -> None:
        """Release libmpv rendering while this widget's GL context is current."""

        self._release_renderer()
        self._player = None

    def prepare_for_window_transition(self) -> None:
        """Release context-owned rendering before an ancestor changes windows."""

        self._release_renderer()

    def complete_window_transition(self) -> None:
        """Request renderer binding after the replacement window becomes live."""

        QTimer.singleShot(0, self._resume_renderer_after_window_transition)

    def initializeGL(self) -> None:  # noqa: N802
        """Initialize libmpv after Qt makes the surface context current."""

        context = self.context()
        if context is not self._observed_context:
            self._observed_context = context
            context.aboutToBeDestroyed.connect(
                partial(self._release_renderer_for_context, context)
            )
        self._initialize_renderer()
        self.renderingReady.emit()

    def paintGL(self) -> None:  # noqa: N802
        """Render the latest decoded frame into Qt's framebuffer."""

        self._clear_framebuffer()
        player = self._player
        if player is None or not self._renderer_initialized:
            return
        ratio = self.devicePixelRatioF()
        player.render_frame(
            framebuffer=self.defaultFramebufferObject(),
            width=max(1, round(self.width() * ratio)),
            height=max(1, round(self.height() * ratio)),
        )
        player.report_swap()

    def resizeGL(self, width: int, height: int) -> None:  # noqa: N802
        """Publish settled surface geometry for actual-size recalculation."""

        del width, height
        self.surfaceResized.emit()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        """Forward video-detail context gestures through the Output owner."""

        self.contextMenuRequested.emit(event.globalPos())
        event.accept()

    def _initialize_renderer(self) -> None:
        """Create the render context once a player and current GL context exist."""

        player = self._player
        if player is None or self._renderer_initialized:
            return
        player.initialize_renderer(self._get_proc_address)
        self._renderer_initialized = True
        self._renderer_context = QOpenGLContext.currentContext()
        self._render_poll.start()
        self.update()

    @Slot()
    def _resume_renderer_after_window_transition(self) -> None:
        """Initialize against the settled context or ask Qt to create one."""

        if self._player is None or self._renderer_initialized:
            return
        if self.context() is None or not self.isValid():
            self.update()
            return
        self.makeCurrent()
        try:
            self._initialize_renderer()
        finally:
            self.doneCurrent()

    @Slot()
    def _poll_frame(self) -> None:
        """Poll libmpv on Qt's GUI thread and repaint only for a new frame."""

        player = self._player
        if player is None or not self._renderer_initialized:
            return
        if player.poll_renderer_update():
            self.update()

    @Slot()
    def _release_renderer(self) -> None:
        """Release native rendering before Qt destroys its OpenGL context."""

        self._render_poll.stop()
        player = self._player
        if player is None or not self._renderer_initialized:
            self._renderer_initialized = False
            self._renderer_context = None
            return
        self._renderer_initialized = False
        self._renderer_context = None
        if self.context() is not None and self.isValid():
            self.makeCurrent()
            try:
                player.release_renderer()
            finally:
                self.doneCurrent()
            return
        player.release_renderer()

    def _release_renderer_for_context(self, context: QOpenGLContext) -> None:
        """Ignore delayed destruction from a superseded surface context."""

        if context is not self._renderer_context:
            return
        self._release_renderer()

    @staticmethod
    def _get_proc_address(name: str) -> int:
        """Resolve one OpenGL symbol from Qt's current context."""

        context = QOpenGLContext.currentContext()
        if context is None:
            return 0
        address = context.getProcAddress(name.encode())
        return int(address) if address is not None else 0


def clear_transparent_opengl_framebuffer() -> None:
    """Clear every current color-buffer pixel to transparent black."""

    context = QOpenGLContext.currentContext()
    if context is None:
        return
    functions = context.functions()
    functions.glDisable(_GL_SCISSOR_TEST)
    functions.glColorMask(True, True, True, True)
    functions.glClearColor(0.0, 0.0, 0.0, 0.0)
    functions.glClear(_GL_COLOR_BUFFER_BIT)


__all__ = ["VideoOpenGLSurface"]
