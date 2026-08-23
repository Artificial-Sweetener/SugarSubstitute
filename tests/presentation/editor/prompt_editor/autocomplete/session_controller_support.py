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

"""Shared deterministic support for autocomplete session-controller contracts."""

from __future__ import annotations


from collections.abc import Callable
from typing import Any


from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteCandidate,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession


class _VisibilityRecordingPresenter:
    """Record autocomplete presentation while exposing explicit visibility changes."""

    def __init__(self, *, visible: bool) -> None:
        """Initialize the presenter with a deterministic visible result."""

        self.visible = visible
        self.visibility_handler: Callable[[bool], None] | None = None
        self.presented_sessions: list[AutocompleteSession] = []

    @property
    def panel(self) -> None:
        """Return no concrete panel for coordinator tests."""

        return None

    def present_session(self, session: AutocompleteSession) -> bool:
        """Record one present request and return the configured visibility."""

        self.presented_sessions.append(session)
        return self.visible

    def set_activation_handler(self, handler: Callable[[Any], None] | None) -> None:
        """Accept activation wiring without using it."""

        _ = handler

    def set_selection_changed_handler(
        self,
        handler: Callable[[int], None] | None,
    ) -> None:
        """Accept selection wiring without using it."""

        _ = handler

    def set_visibility_changed_handler(
        self,
        handler: Callable[[bool], None] | None,
    ) -> None:
        """Store the visibility callback supplied by the coordinator."""

        self.visibility_handler = handler

    def panel_under_mouse(self) -> bool:
        """Return whether the panel is visible for focus-retention checks."""

        return self.visible

    def activate(self, intent: Any) -> None:
        """Accept activation forwarding without using it."""

        _ = intent

    def current_index(self) -> int:
        """Return no selected panel index for coordinator tests."""

        return -1

    def panel_visible(self) -> bool:
        """Return the configured panel visibility state."""

        return self.visible

    def hide(self) -> None:
        """Hide the panel and publish the visibility transition."""

        self.set_visible(False)

    def move_lora_selection(self, direction: str) -> int | None:
        """Return no panel-owned LoRA movement for these tests."""

        _ = direction
        return None

    def set_visible(self, visible: bool) -> None:
        """Apply a visible-state transition through the stored callback."""

        self.visible = visible
        handler = self.visibility_handler
        if callable(handler):
            handler(visible)


def _lora_candidate(prompt_name: str) -> PromptLoraAutocompleteCandidate:
    """Return one deterministic LoRA autocomplete candidate."""

    item = PromptLoraCatalogItem(
        display_name=prompt_name.title(),
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder="",
        basename=prompt_name,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=prompt_name.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=prompt_name.casefold(),
    )
    return PromptLoraAutocompleteCandidate(
        item=item,
        score=10,
        display_text=prompt_name.title(),
        display_completion_suffix="",
        replacement_text=f"<lora:{prompt_name}:1>",
        match_kind="display",
    )
