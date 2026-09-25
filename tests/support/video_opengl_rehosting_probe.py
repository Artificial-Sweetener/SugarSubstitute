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

"""Run the video render-surface rehosting contract on native Qt."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.presentation.canvas.output.video_opengl_surface import (
    VideoOpenGLSurface,
)
from tests.support.qt.lifecycle import destroy_widget_roots
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _RenderPlayer:
    """Record renderer ownership across concrete Qt OpenGL contexts."""

    def __init__(self) -> None:
        """Initialize lifecycle and frame counters."""

        self.initializations: list[Callable[[str], int]] = []
        self.releases = 0
        self.frames = 0
        self.swaps = 0

    def initialize_renderer(self, get_proc_address: Callable[[str], int]) -> None:
        """Record renderer initialization for the current context generation."""

        self.initializations.append(get_proc_address)

    def poll_renderer_update(self) -> bool:
        """Request continuous test repainting."""

        return True

    def render_frame(self, *, framebuffer: int, width: int, height: int) -> None:
        """Record one positive-sized framebuffer render."""

        if framebuffer < 0 or width <= 0 or height <= 0:
            raise AssertionError("Qt supplied an invalid OpenGL framebuffer.")
        self.frames += 1

    def report_swap(self) -> None:
        """Record one presented frame."""

        self.swaps += 1

    def release_renderer(self) -> None:
        """Record renderer release before its context disappears."""

        self.releases += 1


def main() -> int:
    """Prove docked, floating, and redocked rendering in one native process."""

    application = QApplication([])
    player = _RenderPlayer()
    docked = QWidget()
    floating = QWidget()
    docked.setWindowOpacity(0.0)
    floating.setWindowOpacity(0.0)
    docked_layout = QVBoxLayout(docked)
    floating_layout = QVBoxLayout(floating)
    surface = VideoOpenGLSurface()
    try:
        docked_layout.addWidget(surface)
        docked.resize(640, 480)
        floating.resize(640, 480)
        docked.show()
        wait_for_qt_condition(
            lambda: surface.rendering_ready,
            description="initial docked OpenGL context",
        )
        surface.bind_player(player)  # type: ignore[arg-type]
        wait_for_qt_condition(
            lambda: len(player.initializations) == 1 and player.frames > 0,
            description="initial docked video frame",
        )

        surface.prepare_for_window_transition()
        floating_layout.addWidget(surface)
        floating.show()
        surface.complete_window_transition()
        wait_for_qt_condition(
            lambda: len(player.initializations) == 2 and player.releases == 1,
            description="floating renderer recreation",
            state=lambda: (len(player.initializations), player.releases),
        )
        floating_frames = player.frames
        wait_for_qt_condition(
            lambda: player.frames > floating_frames,
            description="floating video frame",
        )

        surface.prepare_for_window_transition()
        docked_layout.addWidget(surface)
        docked.show()
        surface.complete_window_transition()
        wait_for_qt_condition(
            lambda: len(player.initializations) == 3 and player.releases == 2,
            description="redocked renderer recreation",
            state=lambda: (len(player.initializations), player.releases),
        )
        redocked_frames = player.frames
        wait_for_qt_condition(
            lambda: player.frames > redocked_frames,
            description="redocked video frame",
        )
        if player.swaps != player.frames:
            raise AssertionError("Every rendered frame must report its swap.")
        return 0
    finally:
        destroy_widget_roots((floating, docked))
        application.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
