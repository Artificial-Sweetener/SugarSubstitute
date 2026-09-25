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

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QOpenGLContext
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget

from substitute.application.ports.video import VideoOpenGLPlayerPort, VideoPlayerPort


class VideoOpenGLSurface(QOpenGLWidget):
    """Render video as Qt content so chrome and pointer input remain authoritative."""

    frameRequested = Signal()
    surfaceResized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an initially unbound black OpenGL surface."""

        super().__init__(parent)
        self.setObjectName("outputVideoRenderSurface")
        self._player: VideoOpenGLPlayerPort | None = None
        self._renderer_initialized = False
        self.frameRequested.connect(self._queue_update)

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

    def release_player(self) -> None:
        """Release libmpv rendering while this widget's GL context is current."""

        player = self._player
        initialized = self._renderer_initialized
        self._player = None
        self._renderer_initialized = False
        if player is None or not initialized:
            return
        if self.context() is not None and self.isValid():
            self.makeCurrent()
            try:
                player.release_renderer()
            finally:
                self.doneCurrent()
        else:
            player.release_renderer()

    def initializeGL(self) -> None:  # noqa: N802
        """Initialize libmpv after Qt makes the surface context current."""

        self._initialize_renderer()

    def paintGL(self) -> None:  # noqa: N802
        """Render the latest decoded frame into Qt's framebuffer."""

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

    def _initialize_renderer(self) -> None:
        """Create the render context once a player and current GL context exist."""

        player = self._player
        if player is None or self._renderer_initialized:
            return
        player.initialize_renderer(self._get_proc_address, self.frameRequested.emit)
        self._renderer_initialized = True

    @staticmethod
    def _get_proc_address(name: str) -> int:
        """Resolve one OpenGL symbol from Qt's current context."""

        context = QOpenGLContext.currentContext()
        if context is None:
            return 0
        address = context.getProcAddress(name.encode())
        return int(address) if address is not None else 0

    @Slot()
    def _queue_update(self) -> None:
        """Schedule repaint on the Qt GUI thread."""

        self.update()


__all__ = ["VideoOpenGLSurface"]
