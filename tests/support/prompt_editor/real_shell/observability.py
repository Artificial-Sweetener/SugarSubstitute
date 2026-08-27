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

"""Observe production prompt-editor owner calls without changing their behavior."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorObservedEvent,
    PromptFieldHandle,
)


class PromptEditorObservability:
    """Passively record production-owner calls for a mounted prompt editor."""

    def __init__(
        self,
        *,
        enabled: bool,
        observed_events: list[PromptEditorObservedEvent],
        compact_state: Callable[[PromptEditor], Mapping[str, Any]],
        result_formatter: Callable[[object], str],
    ) -> None:
        """Bind passive call recording to one session-owned event collection."""

        self._enabled = enabled
        self._observed_events = observed_events
        self._compact_state = compact_state
        self._result_formatter = result_formatter
        self._observed_editor_ids: set[int] = set()

    def install(self, field: PromptFieldHandle) -> None:
        """Wrap production editor collaborators with passive call tracing."""

        if not self._enabled:
            return
        editor = field.editor
        if id(editor) in self._observed_editor_ids:
            return
        self._observed_editor_ids.add(id(editor))
        surface = getattr(editor, "_surface", None)
        interaction = getattr(editor, "_interaction_controller", None)
        autocomplete = getattr(interaction, "_autocomplete", None)
        autocomplete_timing = getattr(
            interaction,
            "_autocomplete_timing_controller",
            None,
        )
        autocomplete_preview_projection = getattr(
            surface,
            "_autocomplete_preview_projection_owner",
            None,
        )
        caret_preview_coordinator = getattr(
            surface,
            "_caret_autocomplete_preview_coordinator",
            None,
        )
        caret_movement_controller = getattr(
            surface,
            "_caret_movement_controller",
            None,
        )
        text_mutations = getattr(surface, "_text_mutations", None)
        observed_targets = (
            (
                editor,
                "prompt editor event route",
                (
                    "_handle_prompt_key_press",
                    "focusOutEvent",
                    "hideEvent",
                    "set_autocomplete_preview_state",
                ),
            ),
            (
                interaction,
                "prompt editor interaction controller",
                (
                    "handle_key_press",
                    "handle_post_key_press",
                    "handle_focus_out",
                    "handle_hide",
                ),
            ),
            (
                autocomplete,
                "autocomplete lifecycle owner",
                (
                    "handle_key_press",
                    "dismiss_autocomplete",
                    "retarget_from_query_state",
                ),
            ),
            (
                getattr(autocomplete, "_session_publication", None),
                "autocomplete session publication owner",
                (
                    "publish_result",
                    "retarget_from_query_state",
                    "move_suggestion_selection",
                    "move_lora_selection",
                    "dismiss",
                    "refresh_geometry",
                ),
            ),
            (
                autocomplete_timing,
                "autocomplete timing owner",
                (
                    "handle_post_key_press",
                    "handle_focus_out",
                    "handle_hide",
                    "_retarget_from_current_state",
                    "_retarget_from_source_snapshot",
                ),
            ),
            (
                surface,
                "projection source and caret owner",
                (
                    "set_autocomplete_preview_state",
                    "_backspace",
                    "_delete",
                    "_flush_pending_projection_update",
                    "_mark_source_text_changed",
                    "clear_autocomplete_preview_state",
                    "invalidate_autocomplete_preview_paint",
                ),
            ),
            (
                text_mutations,
                "projection text mutation owner",
                ("insert_text", "replace_text", "_commit"),
            ),
            (
                autocomplete_preview_projection,
                "autocomplete preview projection owner",
                ("set_preview_state",),
            ),
            (
                caret_preview_coordinator,
                "caret autocomplete preview coordinator",
                ("reconcile_after_caret_state_change",),
            ),
            (
                caret_movement_controller,
                "projection caret movement owner",
                ("move_horizontally", "move_vertically"),
            ),
        )
        for target, owner, method_names in observed_targets:
            for method_name in method_names:
                self._wrap_observed_method(
                    editor=editor,
                    target=target,
                    owner=owner,
                    method_name=method_name,
                )

    def _wrap_observed_method(
        self,
        *,
        editor: PromptEditor,
        target: object | None,
        owner: str,
        method_name: str,
    ) -> None:
        """Install one passive method wrapper when the collaborator exists."""

        if target is None:
            return
        original = getattr(target, method_name, None)
        if not callable(original) or getattr(
            original, "_prompt_harness_wrapped", False
        ):
            return

        def wrapper(*args: object, **kwargs: object) -> object:
            before = self._compact_state(editor)
            result: object = None
            result_repr = "<raised>"
            try:
                result = original(*args, **kwargs)
                result_repr = self._result_formatter(result)
                return result
            finally:
                after = self._compact_state(editor)
                self._observed_events.append(
                    PromptEditorObservedEvent(
                        index=len(self._observed_events),
                        owner=owner,
                        method=method_name,
                        source_before=str(before["source"]),
                        source_after=str(after["source"]),
                        cursor_before=int(before["cursor"]),
                        cursor_after=int(after["cursor"]),
                        preview_before=str(before["preview"]),
                        preview_after=str(after["preview"]),
                        session_before=str(before["session"]),
                        session_after=str(after["session"]),
                        panel_before=str(before["panel"]),
                        panel_after=str(after["panel"]),
                        result=result_repr,
                    )
                )

        setattr(wrapper, "_prompt_harness_wrapped", True)
        setattr(target, method_name, wrapper)
