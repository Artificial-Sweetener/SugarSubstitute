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

"""Own prompt-editor buffer restoration and presentation preferences."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from PySide6.QtCore import QTimer

from substitute.domain.generation.seed_control import SeedControlState
from substitute.presentation.editor.panel.current_field_state_resolver import (
    CurrentEditorFieldStateResolver,
)
from substitute.presentation.editor.panel.field_state_binding import (
    EditorFieldBinding,
)
from substitute.presentation.editor.panel.field_value_store import (
    EditorFieldValueStore,
    mark_cube_state_dirty,
)
from substitute.presentation.editor.panel.prompt_editor_field_preferences import (
    PromptEditorFieldPreferences,
)


class FieldStateCubeStateProtocol(Protocol):
    """Describe cube-state payload access used by field-state persistence."""

    buffer: dict[str, Any]
    dirty: bool
    field_control_states: dict[str, dict[str, SeedControlState]]


class EditorPanelFieldStateHost(Protocol):
    """Describe panel state required for prompt field-state restoration."""

    cube_widgets: Mapping[str, object]
    _cube_states: Mapping[str, FieldStateCubeStateProtocol] | None

    def refresh_prompt_scene_diagnostics(self) -> None:
        """Refresh scene diagnostics after prompt state restoration."""


class PromptFieldStateController:
    """Synchronize prompt source and per-field presentation preferences."""

    def __init__(
        self,
        host: EditorPanelFieldStateHost | None,
        value_store: EditorFieldValueStore,
        state_resolver: CurrentEditorFieldStateResolver,
        prompt_editor_type: type[object],
    ) -> None:
        """Store prompt state collaborators and the concrete editor type."""

        self._host = host
        self._value_store = value_store
        self._state_resolver = state_resolver
        self._prompt_editor_type = prompt_editor_type
        self._preferences = PromptEditorFieldPreferences(mark_cube_state_dirty)

    def sync_all_from_buffers(self) -> None:
        """Restore all prompt-editor widgets from authoritative workflow buffers."""

        host = self._host
        if host is None or not host._cube_states:
            return
        for cube_widget in host.cube_widgets.values():
            self.sync_widget_from_buffers(cube_widget)
        host.refresh_prompt_scene_diagnostics()

    def sync_cube_from_buffers(self, cube_alias: str) -> None:
        """Restore prompt-editor widget values for one cube alias."""

        host = self._host
        if host is None or not host._cube_states:
            return
        cube_widget = host.cube_widgets.get(cube_alias)
        if cube_widget is None:
            return
        self.sync_widget_from_buffers(cube_widget)
        host.refresh_prompt_scene_diagnostics()

    def sync_widget_from_buffers(self, cube_widget: object) -> None:
        """Restore prompt-editor widget values hosted by one cube widget."""

        host = self._host
        if host is None or not host._cube_states:
            return
        for prompt_editor in self._prompt_editors_in(cube_widget):
            binding = EditorFieldBinding.from_widget(prompt_editor)
            if binding is None or binding.cube_alias is None:
                continue
            cube_state = host._cube_states.get(binding.cube_alias)
            if cube_state is None:
                continue
            text_value = self._value_store.field_value(cube_state, binding)
            text = text_value if isinstance(text_value, str) else ""
            if getattr(prompt_editor, "toPlainText")() != text:
                set_prompt_editor_source_text(prompt_editor, text)

    def bind_preferences(
        self,
        prompt_editor: object,
        cube_state: object,
        binding: EditorFieldBinding,
        *,
        manual_height_changed: Callable[[], None] | None,
    ) -> None:
        """Restore and persist prompt rich-rendering and height preferences."""

        field_identity = binding.prompt_field_identity
        if field_identity is None:
            return
        self._restore_rich_rendering(prompt_editor, cube_state, field_identity)
        self._connect_rich_rendering_persistence(
            prompt_editor,
            cube_state,
            field_identity,
            changed_callback=manual_height_changed,
        )
        stored_height = self._preferences.manual_height(cube_state, field_identity)

        def connect_manual_height_persistence() -> None:
            """Persist future user-owned prompt height changes for this field."""

            height_changed = getattr(prompt_editor, "manualScrollHeightChanged", None)
            if height_changed is None:
                return

            def persist_manual_height(height: object) -> None:
                """Store one changed prompt height and notify the shell."""

                changed = self._preferences.store_manual_height(
                    self._state_resolver.resolve(cube_state, binding.cube_alias),
                    field_identity,
                    height,
                )
                if changed and manual_height_changed is not None:
                    manual_height_changed()

            connect_signal(height_changed, persist_manual_height)

        if stored_height is None:
            connect_manual_height_persistence()
            return

        def apply_restored_manual_height() -> None:
            """Apply restored height after prompt text layout has settled."""

            set_manual_height = getattr(prompt_editor, "setManualScrollHeight", None)
            if callable(set_manual_height):
                set_manual_height(stored_height)
            connect_manual_height_persistence()

        QTimer.singleShot(0, apply_restored_manual_height)

    def _prompt_editors_in(self, cube_widget: object) -> tuple[object, ...]:
        """Return prompt-editor children from one cube widget-like object."""

        find_children = getattr(cube_widget, "findChildren", None)
        if not callable(find_children):
            return ()
        return tuple(
            editor
            for editor in find_children(self._prompt_editor_type)
            if isinstance(editor, self._prompt_editor_type)
        )

    def _restore_rich_rendering(
        self,
        prompt_editor: object,
        cube_state: object,
        field_identity: str,
    ) -> None:
        """Apply stored rich-rendering state without marking the cube dirty."""

        stored_enabled = self._preferences.rich_rendering_enabled(
            cube_state,
            field_identity,
        )
        if stored_enabled is None:
            return
        set_enabled = getattr(prompt_editor, "setRichPromptRenderingEnabled", None)
        if callable(set_enabled):
            set_enabled(stored_enabled)

    def _connect_rich_rendering_persistence(
        self,
        prompt_editor: object,
        cube_state: object,
        field_identity: str,
        *,
        changed_callback: Callable[[], None] | None,
    ) -> None:
        """Persist future prompt rich-rendering preference changes for this field."""

        changed_signal = getattr(
            prompt_editor,
            "richPromptRenderingEnabledChanged",
            None,
        )
        if changed_signal is None:
            return

        def persist_rich_rendering(enabled: object) -> None:
            """Store one changed prompt rich-rendering preference."""

            changed = self._preferences.store_rich_rendering_enabled(
                self._state_resolver.resolve_for_field_identity(
                    cube_state,
                    field_identity,
                ),
                field_identity,
                enabled,
            )
            if changed and changed_callback is not None:
                changed_callback()

        connect_signal(changed_signal, persist_rich_rendering)


def set_prompt_editor_source_text(prompt_editor: object, text: str) -> None:
    """Restore prompt source text exactly through the strongest available API."""

    replace_baseline = getattr(prompt_editor, "replaceBaselineSourceText", None)
    if callable(replace_baseline):
        replace_baseline(text)
        return
    set_source_text = getattr(prompt_editor, "setSourceText", None)
    if callable(set_source_text):
        set_source_text(text)
        return
    getattr(prompt_editor, "setPlainText")(text)


def connect_signal(signal: object, slot: Callable[..., None]) -> None:
    """Connect one Qt-like signal when it exposes a connect method."""

    connect = getattr(signal, "connect", None)
    if callable(connect):
        connect(slot)


__all__ = [
    "EditorPanelFieldStateHost",
    "FieldStateCubeStateProtocol",
    "PromptFieldStateController",
    "connect_signal",
    "set_prompt_editor_source_text",
]
