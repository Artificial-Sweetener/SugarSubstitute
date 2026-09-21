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

"""Test projection viewport event arbitration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.interactions import (
    PromptExternalTextInputOwner,
    PromptSurfaceMouseHandler,
    PromptSurfaceWheelHandler,
)
from substitute.presentation.editor.prompt_editor.projection.edit_to_frame import (
    PromptLayoutEditToFrameCoordinator,
)
from substitute.presentation.editor.prompt_editor.projection.viewport_event_router import (
    PromptProjectionViewportEventRouter,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp


class _MouseRecorder:
    """Record viewport pointer routing used by focused tests."""

    def __init__(self) -> None:
        """Create empty pointer event state."""

        self.releases: list[object] = []
        self.clear_count = 0

    def handle_viewport_mouse_release(self, event: object) -> bool:
        """Record and consume one release event."""

        self.releases.append(event)
        return True

    def clear_hovered_token(self, *, update: bool) -> None:
        """Record pointer-state clearing without requiring a mounted host."""

        assert update is False
        self.clear_count += 1


class _WheelRecorder:
    """Record viewport wheel-state cleanup."""

    def __init__(self) -> None:
        """Create an empty cleanup count."""

        self.clear_count = 0

    def clear_boundary_spill(self) -> None:
        """Record one boundary-spill clear."""

        self.clear_count += 1


class _ExternalTextRecorder:
    """Record external drag arbitration."""

    def __init__(self) -> None:
        """Create an empty drag event log."""

        self.drag_events: list[object] = []

    def accept_or_ignore_drag(self, event: object) -> bool:
        """Record and accept one drag event."""

        self.drag_events.append(event)
        return True


def _router(
    viewport: QWidget,
) -> tuple[
    PromptProjectionViewportEventRouter,
    _MouseRecorder,
    _WheelRecorder,
    _ExternalTextRecorder,
]:
    """Build a router with focused controller recorders."""

    mouse = _MouseRecorder()
    wheel = _WheelRecorder()
    external_text = _ExternalTextRecorder()
    router = PromptProjectionViewportEventRouter(
        viewport=viewport,
        layout=cast(
            PromptLayoutEditToFrameCoordinator,
            SimpleNamespace(frame=object()),
        ),
        mouse=cast(PromptSurfaceMouseHandler, mouse),
        wheel=cast(PromptSurfaceWheelHandler, wheel),
        external_text=cast(PromptExternalTextInputOwner, external_text),
        parent=viewport,
    )
    return router, mouse, wheel, external_text


def test_viewport_filter_routes_release_and_external_drag_to_focused_owners() -> None:
    """Filtered pointer and drag events should reach their authoritative owners."""

    ensure_qapp()
    viewport = QWidget()
    router, mouse, _, external_text = _router(viewport)
    release = QEvent(QEvent.Type.MouseButtonRelease)
    drag_enter = QEvent(QEvent.Type.DragEnter)

    assert router.eventFilter(viewport, release) is True
    assert router.eventFilter(viewport, drag_enter) is True

    assert mouse.releases == [release]
    assert external_text.drag_events == [drag_enter]


def test_viewport_leave_clears_pointer_and_wheel_state() -> None:
    """Target-side leave handling should clear all pointer-local transient state."""

    ensure_qapp()
    viewport = QWidget()
    router, mouse, wheel, _ = _router(viewport)

    assert router.handle_viewport_event(QEvent(QEvent.Type.Leave)) is None

    assert mouse.clear_count == 1
    assert wheel.clear_count == 1
