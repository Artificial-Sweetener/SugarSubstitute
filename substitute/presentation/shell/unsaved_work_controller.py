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

"""Present Save, Don't Save, or Cancel at destructive workflow boundaries."""

from __future__ import annotations

from typing import Any, Protocol, cast

from PySide6.QtWidgets import QMessageBox, QWidget

from substitute.application.workflows.unsaved_work_service import (
    UnsavedWorkDecision,
)
from sugarsubstitute_shared.presentation.localization import app_text


class UnsavedWorkPrompt(Protocol):
    """Choose how one dirty workflow should be handled."""

    def decide(
        self,
        *,
        parent: QWidget,
        workflow_name: str,
    ) -> UnsavedWorkDecision:
        """Return the user's explicit dirty-document decision."""


class QtUnsavedWorkPrompt:
    """Render the localized native dirty-document decision dialog."""

    def decide(
        self,
        *,
        parent: QWidget,
        workflow_name: str,
    ) -> UnsavedWorkDecision:
        """Ask whether to save, discard, or cancel the destructive action."""

        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(app_text("Unsaved work"))
        dialog.setText(
            app_text(
                "Save changes to “%1” before continuing?",
                workflow_name,
            )
        )
        dialog.setInformativeText(
            app_text(
                "A recovery copy is kept, but explicit saves are the durable project file."
            )
        )
        save_button = dialog.addButton(
            app_text("Save"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard_button = dialog.addButton(
            app_text("Don't Save"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = dialog.addButton(
            app_text("Cancel"),
            QMessageBox.ButtonRole.RejectRole,
        )
        dialog.setDefaultButton(cast(Any, save_button))
        dialog.setEscapeButton(cast(Any, cancel_button))
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is save_button:
            return UnsavedWorkDecision.SAVE
        if clicked is discard_button:
            return UnsavedWorkDecision.DISCARD
        return UnsavedWorkDecision.CANCEL


class UnsavedWorkController:
    """Coordinate dirty-document decisions with shell save and activation owners."""

    def __init__(
        self,
        shell: Any,
        *,
        prompt: UnsavedWorkPrompt | None = None,
    ) -> None:
        """Store the shell and the user-decision boundary."""

        self._shell = shell
        self._prompt = prompt or QtUnsavedWorkPrompt()

    def confirm_workflow_close(self, workflow_id: str) -> bool:
        """Return whether one workflow may be closed without losing work."""

        state = self._shell.unsaved_work_service.state_for(workflow_id)
        if not state.dirty:
            return True
        return self._resolve_workflow(workflow_id)

    def confirm_shutdown(self) -> bool:
        """Resolve every dirty workflow before maintenance or app shutdown."""

        ordered_ids = tuple(self._shell.workflow_tabbar.workflow_ids_in_order())
        dirty_ids = self._shell.unsaved_work_service.dirty_workflow_ids(ordered_ids)
        return all(self._resolve_workflow(workflow_id) for workflow_id in dirty_ids)

    def _resolve_workflow(self, workflow_id: str) -> bool:
        """Apply one explicit dirty-work decision and report continuation."""

        item = self._shell.workflow_tabbar.itemMap.get(workflow_id)
        workflow_name = item.text() if item is not None else workflow_id
        decision = self._prompt.decide(
            parent=cast(QWidget, self._shell),
            workflow_name=str(workflow_name),
        )
        if decision is UnsavedWorkDecision.CANCEL:
            return False
        if decision is UnsavedWorkDecision.DISCARD:
            return True
        active_id = self._shell.workflow_session_service.active_workflow_id
        if active_id != workflow_id:
            self._shell.workflow_workspace.activate_workflow(
                workflow_id,
                source="unsaved_work_save",
            )
        return bool(self._shell.workspace_file_actions.on_save_clicked())


__all__ = [
    "QtUnsavedWorkPrompt",
    "UnsavedWorkController",
    "UnsavedWorkPrompt",
]
