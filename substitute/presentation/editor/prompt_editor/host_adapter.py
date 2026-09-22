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

"""Adapt mounted prompt-editor owners to QFluent host callbacks."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QRect
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QScrollBar, QWidget

from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptSyntaxAction,
)
from substitute.presentation.widgets.wheel_permission import wheel_event_is_allowed

from .interactions import PromptWheelScrollResult
from .qt_lifecycle import qt_object_is_alive
from .runtime_mount import PromptEditorRuntimeMount
from .shell import PromptShellChromeSurface, PromptShellScrollSurface


class PromptEditorHostAdapter:
    """Bridge the mounted owner graph to shell, surface, and panel callbacks."""

    def __init__(
        self,
        *,
        host: QWidget,
        shell_viewport: QWidget,
        host_scrollbar: QScrollBar,
        runtime: PromptEditorRuntimeMount,
        apply_host_placeholder: Callable[[str], None],
        publish_text_changed: Callable[[], None],
    ) -> None:
        """Store stable host objects and resolve staged runtime owners on demand."""

        self._host = host
        self._shell_viewport = shell_viewport
        self._host_scrollbar = host_scrollbar
        self._runtime = runtime
        self._apply_host_placeholder = apply_host_placeholder
        self._publish_text_changed = publish_text_changed

    @property
    def shell_viewport(self) -> QWidget:
        """Return the real QFluent viewport beneath the projection surface."""

        return self._shell_viewport

    def content_viewport(self) -> QWidget | None:
        """Return the projection viewport after projection construction."""

        projection = self._runtime.projection_or_none
        return projection.surface.viewport() if projection is not None else None

    def apply_host_placeholder(self, text: str) -> None:
        """Apply visible placeholder text through QFluent's native implementation."""

        self._apply_host_placeholder(text)

    def chrome_surface(self) -> PromptShellChromeSurface | None:
        """Return the mounted projection through the chrome surface boundary."""

        projection = self._runtime.projection_or_none
        surface = projection.surface if projection is not None else None
        return cast(PromptShellChromeSurface | None, surface)

    def scroll_surface(self) -> PromptShellScrollSurface | None:
        """Return the mounted projection through the scroll surface boundary."""

        projection = self._runtime.projection_or_none
        surface = projection.surface if projection is not None else None
        return cast(PromptShellScrollSurface | None, surface)

    def shell_padding_fill_plane(self) -> QWidget | None:
        """Return the shell-padding fill plane after projection construction."""

        projection = self._runtime.projection_or_none
        fill_plane = (
            projection.shell_padding_fill_plane if projection is not None else None
        )
        return fill_plane if isinstance(fill_plane, QWidget) else None

    def fill_plane(self) -> QWidget | None:
        """Return the projection viewport fill plane after construction."""

        projection = self._runtime.projection_or_none
        fill_plane = projection.fill_plane if projection is not None else None
        return fill_plane if isinstance(fill_plane, QWidget) else None

    def token_weight_controls(self) -> QWidget | None:
        """Return mounted token-weight controls after core construction."""

        core = self._runtime.core_or_none
        controls = core.syntax.token_weight_controls if core is not None else None
        return controls if isinstance(controls, QWidget) else None

    def update_backing_fill(self, rect: QRect) -> None:
        """Repaint shell-owned fill layers for one dirty projection rectangle."""

        projection = self._runtime.projection_or_none
        if projection is None:
            return
        self._runtime.shell.shell.update_backing_fill(
            rect=rect,
            surface=projection.surface,
            fill_plane=projection.fill_plane,
            shell_padding_fill_plane=projection.shell_padding_fill_plane,
        )

    def finish_pending_key_edit_block(self, reason: str) -> None:
        """Finish pending projection key editing before a shell transition."""

        self._runtime.projection.edit_execution.finish_pending_key_edit_block(
            reason=reason
        )

    def schedule_lora_metadata_catchup(self) -> None:
        """Schedule visible LoRA metadata catch-up through its feature owner."""

        self._runtime.features.catalog_refresh.schedule_lora_metadata_catchup_if_needed()

    def handle_focus_out(self) -> None:
        """Forward deferred focus-out cleanup to the interaction owner."""

        self._runtime.core.syntax.interaction_controller.handle_focus_out()

    def handle_hide(self) -> None:
        """Forward editor-hide cleanup to the interaction owner."""

        self._runtime.core.syntax.interaction_controller.handle_hide()

    def handle_move(self) -> None:
        """Forward editor movement to the interaction owner."""

        self._runtime.core.syntax.interaction_controller.handle_move()

    def handle_viewport_wheel_event(self, event: QWheelEvent) -> bool:
        """Route viewport wheel input through the policy-aware owner."""

        return self._runtime.core.syntax.wheel_controller.handle_viewport_wheel_event(
            event
        )

    def host_scrollbar(self) -> QScrollBar:
        """Return QFluent's native host scrollbar for metric mirroring."""

        return self._host_scrollbar

    def handle_viewport_scroll(self) -> None:
        """Forward viewport scroll work to the interaction owner."""

        self._runtime.core.syntax.interaction_controller.handle_viewport_scroll()

    def handle_resize(self) -> None:
        """Forward resize work to the interaction owner."""

        self._runtime.core.syntax.interaction_controller.handle_resize()

    def surface_content_height(self) -> float:
        """Return the mounted projection's live content height."""

        projection = self._runtime.projection_or_none
        return float(projection.surface.content_height()) if projection else 0.0

    def projection_line_height(self) -> float:
        """Return projection-owned text row height or a safe construction default."""

        projection = self._runtime.projection_or_none
        return float(projection.surface.text_line_height()) if projection else 1.0

    def surface_is_alive(self) -> bool:
        """Return whether the mounted surface can still serve sizing data."""

        projection = self._runtime.projection_or_none
        return projection is not None and qt_object_is_alive(projection.surface)

    def update_fill_planes(self) -> None:
        """Repaint both shell fill planes after a sizing change."""

        projection = self._runtime.projection_or_none
        if projection is None:
            return
        projection.shell_padding_fill_plane.update()
        projection.fill_plane.update()

    def resize_handle(self) -> QWidget | None:
        """Return the shell resize handle after host integration."""

        host = self._runtime.host_or_none
        resize_handle = host.resize_handle if host is not None else None
        return resize_handle if isinstance(resize_handle, QWidget) else None

    def ancestor_external_wheel_handler(self) -> QWidget | None:
        """Return the nearest ancestor that owns editor-panel wheel scrolling."""

        current = self._host.parentWidget()
        while current is not None:
            if callable(getattr(current, "handle_external_wheel", None)):
                return current
            current = current.parentWidget()
        return None

    def allow_surface_wheel_scroll(self, event: QWheelEvent) -> bool:
        """Return whether surface wheel scrolling may consume one event."""

        return self._runtime.core.syntax.wheel_controller.allow_surface_wheel_scroll(
            event
        )

    def handle_surface_wheel_scroll(
        self,
        event: QWheelEvent,
    ) -> PromptWheelScrollResult:
        """Route a wheel event to the projection surface scroll owner."""

        return self._runtime.projection.surface.handle_prompt_wheel_scroll(event)

    def surface_wheel_event_is_allowed(self, event: QWheelEvent) -> bool:
        """Return whether configured wheel intent permits surface consumption."""

        return wheel_event_is_allowed(self._host, event)

    def forward_wheel_event_to_editor_panel(self, event: QWheelEvent) -> None:
        """Forward intentionally bubbled prompt wheel input to its panel ancestor."""

        panel = self.ancestor_external_wheel_handler()
        if panel is None:
            event.ignore()
            return
        handler = cast(
            Callable[[QWheelEvent], None],
            getattr(panel, "handle_external_wheel"),
        )
        handler(event)

    def handle_surface_text_changed(self) -> None:
        """Synchronize shell chrome and publish one public text-change signal."""

        self._runtime.shell.chrome.apply_placeholder_visibility()
        self._runtime.shell.chrome.update_fill_planes()
        self._publish_text_changed()

    def handle_surface_syntax_action(self, action: PromptSyntaxAction) -> None:
        """Route one surface syntax action to the weight feature owner."""

        self._runtime.core.syntax.weight_interaction.apply_syntax_action(action)

    def handle_surface_mouse_release(self) -> None:
        """Refresh autocomplete after a surface-owned mouse interaction."""

        self._runtime.core.syntax.interaction_controller.handle_mouse_release()

    @staticmethod
    def prompt_menu_requires_custom_actions() -> bool:
        """Require the prompt-specific context menu for every prompt editor."""

        return True


__all__ = [
    "PromptEditorHostAdapter",
]
