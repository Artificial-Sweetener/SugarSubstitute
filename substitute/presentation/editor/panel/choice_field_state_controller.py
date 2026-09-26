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

"""Own linked sampler and scheduler choice persistence."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from substitute.application.overrides.link_policy import apply_choice_selection
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
from substitute.presentation.editor.panel.prompt_field_state_controller import (
    connect_signal,
)


class ChoiceFieldStateController:
    """Bind link-aware choice widgets to authoritative field state."""

    def __init__(
        self,
        value_store: EditorFieldValueStore,
        state_resolver: CurrentEditorFieldStateResolver,
    ) -> None:
        """Store field value and current-state collaborators."""

        self._value_store = value_store
        self._state_resolver = state_resolver

    def bind_linked_choice(
        self,
        combo: object,
        cube_state: object,
        binding: EditorFieldBinding,
    ) -> bool:
        """Bind sampler/scheduler link-aware selections when applicable."""

        link_key = self._link_key(binding)
        if link_key is None:
            return False
        node = self._value_store.node_payload(cube_state, binding)
        if node is None:
            return False
        label_to_value = getattr(combo, "_editor_choice_values_by_label", None)
        if not isinstance(label_to_value, Mapping):
            return self._bind_literal_choice(
                combo,
                cube_state,
                binding,
                node,
                link_key,
            )

        if not isinstance(node.get(link_key), dict):
            current = self._value_store.field_value(cube_state, binding)
            if current is not None and getattr(combo, "currentText")() != str(current):
                getattr(combo, "setCurrentText")(str(current))

        def on_changed(text: str) -> None:
            """Persist the selected literal or link through the field-state owner."""

            current_state = self._state_resolver.resolve(
                cube_state,
                binding.cube_alias,
            )
            current_node = self._value_store.mutable_node_payload(
                current_state,
                binding,
            )
            if current_node is None:
                return
            selected_value = label_to_value.get(text)
            before = deepcopy(current_node)
            apply_choice_selection(
                current_node,
                literal_key=binding.field_key,
                link_key=link_key,
                selected_value=selected_value,
            )
            if current_node != before:
                mark_cube_state_dirty(current_state)
                self._value_store.notify_field_value_changed(
                    binding,
                    self._value_store.field_value(current_state, binding),
                )

        connect_signal(string_signal(getattr(combo, "currentTextChanged")), on_changed)
        return True

    def _bind_literal_choice(
        self,
        combo: object,
        cube_state: object,
        binding: EditorFieldBinding,
        node: dict[str, object],
        link_key: str,
    ) -> bool:
        """Bind a literal combo when a legacy active link may need clearing."""

        if not isinstance(node.get(link_key), dict):
            return False

        def on_literal_changed(text: str) -> None:
            """Persist a literal selection and clear the active link."""

            current_state = self._state_resolver.resolve(
                cube_state,
                binding.cube_alias,
            )
            current_node = self._value_store.mutable_node_payload(
                current_state,
                binding,
            )
            if (
                current_node is not None
                and not text.startswith("🔗 ")
                and link_key in current_node
            ):
                del current_node[link_key]
            self._value_store.set_field_value(current_state, binding, text)

        connect_signal(
            string_signal(getattr(combo, "currentTextChanged")),
            on_literal_changed,
        )
        return True

    @staticmethod
    def _link_key(binding: EditorFieldBinding) -> str | None:
        """Return the companion link key for a supported choice field."""

        if binding.field_key == "sampler_name":
            return "sampler_link"
        if binding.field_key == "scheduler":
            return "scheduler_link"
        return None


def string_signal(signal: object) -> object:
    """Return a string overload signal where Qt exposes one."""

    try:
        return signal[str]  # type: ignore[index]
    except (KeyError, TypeError, AttributeError):
        return signal


__all__ = ["ChoiceFieldStateController", "string_signal"]
