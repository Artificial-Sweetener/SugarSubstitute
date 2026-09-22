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

"""Own scene-context publication for one mounted prompt editor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from .features import (
    PromptAutocompleteQueryResultLifecycle,
    PromptSceneContextPublication,
)


@dataclass(frozen=True, slots=True)
class PromptEditorSceneBindings:
    """Declare scene publication and dependent-refresh operations."""

    metadata: Callable[[], object]
    set_context_identity: Callable[..., None]
    set_autocomplete_titles: Callable[[tuple[str, ...]], None]
    set_queueable_keys: Callable[[frozenset[str]], None]
    refresh_active_autocomplete_session: Callable[[], None]


@dataclass(frozen=True, slots=True)
class PromptEditorSceneFacade:
    """Publish scene context with one stable editor metadata identity."""

    bindings: PromptEditorSceneBindings

    def set_autocomplete_titles(self, titles: tuple[str, ...]) -> None:
        """Publish scene titles and refresh the active dependent query."""

        self._refresh_context_identity()
        self.bindings.set_autocomplete_titles(titles)
        self.bindings.refresh_active_autocomplete_session()

    def set_queueable_keys(self, scene_keys: frozenset[str]) -> None:
        """Publish scene keys eligible for context-menu queue actions."""

        self._refresh_context_identity()
        self.bindings.set_queueable_keys(scene_keys)

    def _refresh_context_identity(self) -> None:
        """Derive the scene publication identity from current field metadata."""

        metadata = self.bindings.metadata()
        if not isinstance(metadata, dict):
            self.bindings.set_context_identity(
                cube_context_id=None,
                scene_context_id=None,
            )
            return
        context_id = (
            metadata.get("cube_alias"),
            metadata.get("node_name"),
            metadata.get("key"),
        )
        self.bindings.set_context_identity(
            cube_context_id=context_id,
            scene_context_id=context_id,
        )


def build_prompt_editor_scene_facade(
    editor: QWidget,
    publication: PromptSceneContextPublication,
    autocomplete: PromptAutocompleteQueryResultLifecycle,
) -> PromptEditorSceneFacade:
    """Bind mounted scene owners to the editor's public scene facade."""

    return PromptEditorSceneFacade(
        PromptEditorSceneBindings(
            metadata=lambda: editor.property("input_metadata"),
            set_context_identity=publication.set_context_identity,
            set_autocomplete_titles=publication.set_scene_autocomplete_titles,
            set_queueable_keys=publication.set_queueable_scene_keys,
            refresh_active_autocomplete_session=(
                autocomplete.refresh_active_scene_session
            ),
        )
    )


__all__ = [
    "PromptEditorSceneBindings",
    "PromptEditorSceneFacade",
    "build_prompt_editor_scene_facade",
]
