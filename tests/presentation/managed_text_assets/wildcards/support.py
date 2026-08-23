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

"""Provide wildcard management modal test collaborators."""

from __future__ import annotations


from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
)
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)
from tests.support.execution.runtime_support import (
    immediate_editor_panel_execution_factories,
)
from tests.support.prompt_editor.reorder_pointer_support import (
    PromptReorderPointerTarget,
    drag_prompt_reorder_target_to_global,
    prompt_reorder_pointer_target,
)


def _prompt_runtime_services() -> PromptEditorRuntimeServices:
    """Return production-shaped prompt services for wildcard modal tests."""

    execution_factories = immediate_editor_panel_execution_factories()
    return PromptEditorRuntimeServices(
        autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_task_executor_factory=execution_factories.prompt_task_executor_factory,
        danbooru_lookup_dispatcher_factory=(
            execution_factories.danbooru_lookup_dispatcher_factory
        ),
    )


def _overlay_chip_by_segment_index(
    overlay: QWidget, segment_index: int
) -> PromptReorderPointerTarget:
    """Return one production logical pointer target by segment index."""

    return prompt_reorder_pointer_target(overlay, segment_index)


def _drag_reorder_chip_to_global(
    chip: PromptReorderPointerTarget,
    *,
    global_target: QPoint,
) -> None:
    """Drive one real mouse drag to the supplied global overlay position."""

    drag_prompt_reorder_target_to_global(chip, global_target=global_target)
