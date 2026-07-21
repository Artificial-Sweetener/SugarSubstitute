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

"""Mount production wildcard editors for headless abuse sessions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QGuiApplication, QTextCursor
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_wildcards import PromptWildcardFileManagementService
from substitute.infrastructure.persistence import FilePromptWildcardFileRepository
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from substitute.presentation.managed_text_assets import WildcardManagementOpener
from tests.execution_test_helpers import immediate_editor_panel_execution_factories
from tests.prompt_autocomplete_test_helpers import EmptyPromptAutocompleteGateway
from tests.prompt_projection_test_helpers import StaticPromptWildcardCatalogGateway

from .models import PromptAbuseScenario


@dataclass(frozen=True, slots=True)
class MountedWildcardEditor:
    """Expose one mounted production wildcard editor and its modal owners."""

    editor: PromptEditor
    modal: QWidget
    owner: QWidget | None


@contextmanager
def mount_wildcard_editor(
    scenario: PromptAbuseScenario,
    *,
    artifact_root: Path,
) -> Iterator[MountedWildcardEditor]:
    """Yield one configured offscreen wildcard editor and close every Qt owner."""

    if scenario.editor_kind not in {"wildcard_txt", "wildcard_csv"}:
        raise ValueError(f"Unsupported wildcard editor kind {scenario.editor_kind!r}.")
    if QApplication.instance() is None:
        QApplication([])
    artifact_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="wildcard-abuse-", dir=artifact_root) as directory:
        service = PromptWildcardFileManagementService(
            FilePromptWildcardFileRepository(Path(directory))
        )
        if scenario.editor_kind == "wildcard_csv":
            service.create_csv_file("abuse", scenario.initial_text)
        else:
            service.create_text_file("abuse", scenario.initial_text)
        modal = cast(
            QWidget,
            WildcardManagementOpener(
                wildcard_file_management_service=service,
                prompt_runtime_services=_runtime_services(),
            ).create_modal(None),
        )
        modal_owner = modal.parentWidget()
        editor = cast(PromptEditor, cast(Any, modal)._editor.editor())
        try:
            if modal_owner is not None:
                modal_owner.show()
            modal.show()
            _apply_scenario_editor_size(
                editor,
                editor_frame=cast(QWidget, cast(Any, modal)._editor),
                size=scenario.viewport_size,
            )
            cursor = editor.textCursor()
            cursor.setPosition(
                scenario.cursor_position, QTextCursor.MoveMode.MoveAnchor
            )
            editor.setTextCursor(cursor)
            editor.setFocus()
            _settle_mount_geometry(editor, modal)
            yield MountedWildcardEditor(editor=editor, modal=modal, owner=modal_owner)
        finally:
            modal.close()
            if modal_owner is not None:
                modal_owner.close()
            process_events(cycles=8)
            modal.deleteLater()
            if modal_owner is not None:
                modal_owner.deleteLater()
            QCoreApplication.sendPostedEvents(
                None,
                QEvent.Type.DeferredDelete,
            )


def _apply_scenario_editor_size(
    editor: QWidget,
    *,
    editor_frame: QWidget,
    size: tuple[int, int],
) -> None:
    """Constrain the modal-managed editor to the scenario's hostile viewport size."""

    width, height = size
    editor.setFixedWidth(width)
    editor_frame.setMinimumHeight(0)
    editor_frame.setFixedHeight(height)


def process_events(*, cycles: int) -> None:
    """Drain a bounded number of Qt events for modal lifecycle transitions."""

    for _cycle in range(cycles):
        QGuiApplication.processEvents()


def _settle_mount_geometry(editor: QWidget, modal: QWidget) -> None:
    """Wait for production modal layouts to reach a stable offscreen geometry."""

    previous_geometry: tuple[int, ...] | None = None
    stable_turns = 0
    for _turn in range(256):
        QGuiApplication.processEvents()
        editor_rect = editor.geometry()
        modal_rect = modal.geometry()
        current_geometry = (
            editor_rect.x(),
            editor_rect.y(),
            editor_rect.width(),
            editor_rect.height(),
            modal_rect.x(),
            modal_rect.y(),
            modal_rect.width(),
            modal_rect.height(),
        )
        if current_geometry == previous_geometry:
            stable_turns += 1
            if stable_turns >= 24:
                return
        else:
            stable_turns = 0
            previous_geometry = current_geometry
    raise RuntimeError("Wildcard abuse mount geometry did not stabilize offscreen.")


def _runtime_services() -> PromptEditorRuntimeServices:
    """Return production-shaped prompt services with external work immediate."""

    execution_factories = immediate_editor_panel_execution_factories()
    return PromptEditorRuntimeServices(
        autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_task_executor_factory=(execution_factories.prompt_task_executor_factory),
        danbooru_lookup_dispatcher_factory=(
            execution_factories.danbooru_lookup_dispatcher_factory
        ),
    )


__all__ = ["MountedWildcardEditor", "mount_wildcard_editor", "process_events"]
