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

"""Restore editor viewport position for restored workflow projections."""

from __future__ import annotations

from typing import Any

from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    WorkflowSnapshot,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.editor_viewport_restore")
_RESTORE_VIEWPORT_RANGE_DRIFT_RATIO = 0.25


class EditorViewportRestoreController:
    """Own restored editor viewport selection and scroll application."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose editor panels should be restored."""

        self._shell = shell

    def restore_editor_viewport_for_workflow(
        self,
        snapshot: WorkflowSnapshot,
    ) -> None:
        """Restore editor scroll for one restored workflow after projection settles."""

        workflow_id = snapshot.workflow_id
        editor_panel = self._shell.editor_panels.get(workflow_id)
        if editor_panel is None:
            log_info(
                _LOGGER,
                "Skipped restored editor viewport because panel was missing",
                workflow_id=workflow_id,
            )
            return
        target_alias = self.restore_viewport_target_alias(snapshot)
        viewport = snapshot.editor_viewport
        previous_lifecycle = getattr(self._shell, "_shell_restore_lifecycle", "")
        self._shell._shell_restore_lifecycle = "restoring"
        try:
            if viewport is not None and self.apply_exact_editor_viewport(
                editor_panel,
                viewport,
                workflow_id=workflow_id,
                target_alias=target_alias,
            ):
                return
            self.scroll_restored_editor_to_alias(
                editor_panel,
                workflow_id=workflow_id,
                target_alias=target_alias,
                viewport=viewport,
            )
        finally:
            self._shell._shell_restore_lifecycle = previous_lifecycle

    @staticmethod
    def restore_viewport_target_alias(snapshot: WorkflowSnapshot) -> str | None:
        """Return the best cube alias target for restored viewport fallback."""

        stack_order = list(snapshot.workflow.stack_order)
        stack_aliases = set(stack_order)
        if snapshot.active_cube_alias in stack_aliases:
            return snapshot.active_cube_alias
        viewport = snapshot.editor_viewport
        if viewport is not None and viewport.anchor_cube_alias in stack_aliases:
            return viewport.anchor_cube_alias
        return stack_order[0] if stack_order else None

    @staticmethod
    def apply_exact_editor_viewport(
        editor_panel: object,
        viewport: EditorViewportSnapshot,
        *,
        workflow_id: str,
        target_alias: str | None,
    ) -> bool:
        """Return whether the saved scrollbar value was applied exactly."""

        try:
            scroll = getattr(editor_panel, "scroll")
            scrollbar = scroll.verticalScrollBar()
            current_maximum = max(0, int(scrollbar.maximum()))
            saved_value = max(0, int(viewport.scroll_value))
            saved_maximum = max(0, int(viewport.scroll_maximum))
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Failed to inspect editor scrollbar for viewport restore",
                workflow_id=workflow_id,
                target_alias=target_alias,
                error=repr(error),
            )
            return False
        if current_maximum <= 0:
            log_debug(
                _LOGGER,
                "Skipped exact editor viewport restore because scroll range is empty",
                workflow_id=workflow_id,
                target_alias=target_alias,
                saved_scroll_value=saved_value,
                saved_scroll_maximum=saved_maximum,
                current_scroll_maximum=current_maximum,
            )
            return False
        if saved_value > current_maximum:
            log_debug(
                _LOGGER,
                "Skipped exact editor viewport restore because value exceeds range",
                workflow_id=workflow_id,
                target_alias=target_alias,
                saved_scroll_value=saved_value,
                saved_scroll_maximum=saved_maximum,
                current_scroll_maximum=current_maximum,
            )
            return False
        if not EditorViewportRestoreController.restore_viewport_ranges_compatible(
            saved_maximum,
            current_maximum,
        ):
            log_debug(
                _LOGGER,
                "Skipped exact editor viewport restore because range drifted",
                workflow_id=workflow_id,
                target_alias=target_alias,
                saved_scroll_value=saved_value,
                saved_scroll_maximum=saved_maximum,
                current_scroll_maximum=current_maximum,
            )
            return False
        scrollbar.setValue(saved_value)
        log_debug(
            _LOGGER,
            "Restored exact editor viewport",
            workflow_id=workflow_id,
            target_alias=target_alias,
            saved_scroll_value=saved_value,
            saved_scroll_maximum=saved_maximum,
            current_scroll_maximum=current_maximum,
        )
        return True

    @staticmethod
    def restore_viewport_ranges_compatible(
        saved_maximum: int,
        current_maximum: int,
    ) -> bool:
        """Return whether two scrollbar ranges are close enough for exact restore."""

        if saved_maximum <= 0:
            return True
        return (
            abs(current_maximum - saved_maximum) / saved_maximum
            <= _RESTORE_VIEWPORT_RANGE_DRIFT_RATIO
        )

    @staticmethod
    def scroll_restored_editor_to_alias(
        editor_panel: object,
        *,
        workflow_id: str,
        target_alias: str | None,
        viewport: EditorViewportSnapshot | None,
    ) -> None:
        """Scroll a restored editor to the selected cube when exact restore is unsafe."""

        if target_alias is None:
            log_info(
                _LOGGER,
                "Skipped restored editor viewport alias fallback without target",
                workflow_id=workflow_id,
                viewport_present=viewport is not None,
            )
            return
        scroll_to_cube = getattr(editor_panel, "scroll_to_cube", None)
        if not callable(scroll_to_cube):
            log_warning(
                _LOGGER,
                "Skipped restored editor viewport alias fallback without scroll API",
                workflow_id=workflow_id,
                target_alias=target_alias,
            )
            return
        scroll_to_cube(
            target_alias,
            animated=False,
            only_if_needed=False,
        )
        log_info(
            _LOGGER,
            "Restored editor viewport by cube alias fallback",
            workflow_id=workflow_id,
            target_alias=target_alias,
            viewport_present=viewport is not None,
        )


def editor_viewport_restore_controller_for(
    shell: Any,
) -> EditorViewportRestoreController:
    """Return the composed editor viewport restore controller for a shell."""

    controller = getattr(shell, "editor_viewport_restore_controller", None)
    if isinstance(controller, EditorViewportRestoreController):
        return controller
    controller = EditorViewportRestoreController(shell)
    setattr(shell, "editor_viewport_restore_controller", controller)
    return controller


__all__ = [
    "EditorViewportRestoreController",
    "editor_viewport_restore_controller_for",
]
