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

"""Build direct autocomplete-panel states for overlay contracts."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QWidget

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteCandidate,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.application.prompt_editor.lora.schedule import PromptLoraScheduleService
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompleteLoraWall,
    PromptAutocompleteLoraWallRenderState,
    PromptAutocompletePanel,
    PromptAutocompletePanelRenderState,
    PromptAutocompleteRow,
    PromptAutocompleteRowRenderState,
    PromptLoraWallView,
)


def lora_candidate(
    item: PromptLoraCatalogItem,
    *,
    suffix: str = "itAI Midna",
) -> PromptLoraAutocompleteCandidate:
    """Return one stable LoRA autocomplete candidate."""

    return PromptLoraAutocompleteCandidate(
        item=item,
        score=100,
        display_text=item.display_name or item.basename,
        display_completion_suffix=suffix,
        replacement_text=PromptLoraScheduleService().schedule_text(item),
        match_kind="display_prefix",
    )


def autocomplete_panel(host: QWidget) -> PromptAutocompletePanel:
    """Create an autocomplete panel with the current LoRA wall adapter."""

    panel = PromptAutocompletePanel(host)
    panel.set_lora_wall(
        autocomplete_lora_wall(
            panel,
            thumbnail_cache=PromptLoraThumbnailCache(),
        )
    )
    return panel


def autocomplete_lora_wall(
    parent: QWidget,
    *,
    thumbnail_cache: PromptLoraThumbnailCache,
) -> PromptAutocompleteLoraWall:
    """Create the concrete LoRA wall used by autocomplete panel tests."""

    return cast(
        PromptAutocompleteLoraWall,
        PromptLoraWallView(parent, thumbnail_cache=thumbnail_cache),
    )


def row_texts(row: PromptAutocompleteRow) -> tuple[str, str]:
    """Return the row-owned rendered tag and popularity strings."""

    return row.rendered_tag_text(), row.rendered_secondary_text()


def render_panel_rows(
    panel: PromptAutocompletePanel,
    suggestions: tuple[PromptAutocompleteSuggestion, ...],
) -> None:
    """Render prepared tag autocomplete rows through the panel state boundary."""

    panel.set_render_state(
        PromptAutocompletePanelRenderState(
            rows=tuple(
                PromptAutocompleteRowRenderState(
                    index=index,
                    title=suggestion.tag,
                    source_label=(
                        suggestion.source_label
                        if suggestion.source_label is not None
                        else (
                            f"{suggestion.popularity:,}"
                            if suggestion.popularity
                            else ""
                        )
                    ),
                    is_selected=index == 0,
                    payload=suggestion,
                )
                for index, suggestion in enumerate(suggestions)
            ),
            visible=True,
        )
    )


def render_panel_lora_candidates(
    panel: PromptAutocompletePanel,
    candidates: tuple[PromptLoraAutocompleteCandidate, ...],
) -> None:
    """Render prepared LoRA autocomplete candidates through the panel boundary."""

    panel.set_render_state(
        PromptAutocompletePanelRenderState(
            lora_wall=PromptAutocompleteLoraWallRenderState(
                items=tuple(candidate.item for candidate in candidates),
                selected_index=0 if candidates else -1,
                activation_payloads=candidates,
            ),
            visible=True,
        )
    )
