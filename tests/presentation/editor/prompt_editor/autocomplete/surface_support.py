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

"""Provide composed PromptEditor support for autocomplete surface contracts."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.danbooru import DanbooruUrlImportService
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptAutocompleteSuggestion,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.execution.runtime_support import (
    immediate_prompt_task_executor_factory,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.support.prompt_editor.projection_engine_support import surface_for


class StaticPromptAutocompleteGateway:
    """Return deterministic autocomplete suggestions for one prefix map."""

    def __init__(
        self,
        results_by_prefix: dict[str, tuple[PromptAutocompleteSuggestion, ...]],
    ) -> None:
        """Store deterministic suggestion tuples keyed by typed prefix."""

        self._results_by_prefix = dict(results_by_prefix)
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Record one query and return the configured suggestion tuple."""

        self.calls.append((prefix, limit))
        return self._results_by_prefix.get(prefix, ())


def create_prompt_editor(
    *,
    parent: QWidget | None = None,
    prompt_autocomplete_gateway: PromptAutocompleteGateway,
    danbooru_url_import_service: object | None = None,
    prompt_feature_profile: PromptEditorFeatureProfile | None = None,
) -> PromptEditor:
    """Create one editor with deterministic autocomplete surface dependencies."""

    return PromptEditor(
        parent,
        prompt_autocomplete_gateway=prompt_autocomplete_gateway,
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        danbooru_url_import_service=cast(
            DanbooruUrlImportService | None,
            danbooru_url_import_service,
        ),
        prompt_feature_profile=prompt_feature_profile,
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )


def editor_autocomplete_preview_text(box: PromptEditor) -> str:
    """Return the surface-owned autocomplete preview suffix when it is active."""

    preview_state = cast(
        Any, getattr(surface_for(box), "_session")
    ).autocomplete_preview
    if preview_state is None:
        return ""
    return cast(str, preview_state.suffix_text)


def has_pending_autocomplete_refresh(box: PromptEditor) -> bool:
    """Return the timing owner's current scheduled-refresh state."""

    interaction = cast(Any, getattr(box, "_interaction_controller"))
    return cast(bool, interaction._autocomplete_timing_controller.has_pending_refresh)


def active_projection_line_texts(box: PromptEditor) -> tuple[str, ...]:
    """Return visual-line text from the active projection layout."""

    layout = getattr(surface_for(box), "_layout")
    snapshot = layout.frame.output.snapshot
    return tuple(
        "".join(
            fragment.text for fragment in line.fragments if hasattr(fragment, "text")
        )
        for line in snapshot.lines
    )
