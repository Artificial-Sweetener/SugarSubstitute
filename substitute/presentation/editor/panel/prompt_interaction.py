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

"""Coordinate prompt-editor diagnostics, search, and wheel interaction."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor.scenes.workflow_analysis import (
    WorkflowSceneAnalysis,
)
from substitute.presentation.editor.prompt_editor import PromptEditor

from .runtime_access import search_controller_for_panel


class EditorPanelPromptInteraction:
    """Provide prompt interaction behavior through the editor panel host API."""

    def configure_wheel_intent_for_widget(self, widget: QWidget) -> None:
        """Attach shared wheel-intent policy to wheel-capable controls."""

        panel: Any = self
        panel._wheel_intent_controller.configure_widget(widget)
        for prompt_editor in self._prompt_wheel_widgets(widget):
            self._configure_prompt_scene_diagnostics(prompt_editor)
            self._configure_prompt_text_search_refresh(prompt_editor)

    def _configure_prompt_scene_diagnostics(
        self,
        prompt_editor: PromptEditor,
    ) -> None:
        """Attach workflow-scene diagnostics refresh to one prompt editor."""

        panel: Any = self
        panel._prompt_scene_diagnostics_controller.configure_prompt_scene_diagnostics(
            prompt_editor
        )

    def _schedule_prompt_scene_diagnostics(self) -> None:
        """Defer scene diagnostics until prompt text reaches workflow buffers."""

        panel: Any = self
        panel._prompt_scene_diagnostics_controller.schedule_prompt_scene_diagnostics()

    def _refresh_scheduled_prompt_scene_diagnostics(self) -> None:
        """Apply one deferred prompt-scene diagnostics refresh."""

        panel: Any = self
        panel._prompt_scene_diagnostics_controller.refresh_scheduled_prompt_scene_diagnostics()

    def _configure_prompt_text_search_refresh(
        self,
        prompt_editor: PromptEditor,
    ) -> None:
        """Attach active search recomputation to one prompt editor."""

        search_controller_for_panel(self).configure_prompt_text_search_refresh(
            prompt_editor
        )

    def _schedule_text_search_refresh(self) -> None:
        """Schedule active text-search ranges after prompt edits."""

        search_controller_for_panel(self).schedule_text_search_refresh()

    def refresh_prompt_scene_diagnostics(self) -> None:
        """Push current workflow scene diagnostics into live prompt editors."""

        panel: Any = self
        panel._prompt_scene_diagnostics_controller.refresh_prompt_scene_diagnostics()

    def _clear_prompt_scene_diagnostics(self) -> None:
        """Clear scene diagnostics from all live prompt editors."""

        panel: Any = self
        panel._prompt_scene_diagnostics_controller.clear_prompt_scene_diagnostics()

    def _current_prompt_scene_analysis(self) -> WorkflowSceneAnalysis | None:
        """Return current workflow scene analysis when editor state is ready."""

        panel: Any = self
        return cast(
            WorkflowSceneAnalysis | None,
            panel._prompt_scene_diagnostics_controller.current_prompt_scene_analysis(),
        )

    def _handle_prompt_scene_queue_requested(self, scene_key: str) -> None:
        """Forward one scene queue request when the scene is runnable."""

        panel: Any = self
        panel._prompt_scene_diagnostics_controller.handle_prompt_scene_queue_requested(
            scene_key
        )

    def _prompt_wheel_widgets(self, widget: QWidget) -> tuple[PromptEditor, ...]:
        """Return unique prompt editors contained by one field widget."""

        widgets: list[PromptEditor] = []
        if isinstance(widget, PromptEditor):
            widgets.append(widget)
        widgets.extend(widget.findChildren(PromptEditor))
        unique_widgets: list[PromptEditor] = []
        seen_ids: set[int] = set()
        for candidate in widgets:
            candidate_id = id(candidate)
            if candidate_id in seen_ids:
                continue
            seen_ids.add(candidate_id)
            unique_widgets.append(candidate)
        return tuple(unique_widgets)

    def handle_external_wheel(self, event: QWheelEvent) -> None:
        """Apply a wheel event routed from adjacent workspace navigation chrome."""

        panel: Any = self
        panel._cancel_active_cube_reveal_scroll()
        viewport = panel.scroll.viewport()
        local_position = viewport.mapFromGlobal(event.globalPosition().toPoint())
        if not viewport.rect().contains(local_position):
            local_position = viewport.rect().center()
        global_position = viewport.mapToGlobal(local_position)
        forwarded_event = QWheelEvent(
            QPointF(local_position),
            QPointF(global_position),
            event.pixelDelta(),
            event.angleDelta(),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted(),
        )
        QApplication.sendEvent(viewport, forwarded_event)
        if forwarded_event.isAccepted():
            event.accept()
            return
        event.ignore()


__all__ = ["EditorPanelPromptInteraction"]
