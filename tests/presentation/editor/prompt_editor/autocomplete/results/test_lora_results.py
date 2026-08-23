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

"""Baseline Phase 27 autocomplete behavior before SOC extraction."""

from __future__ import annotations


from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteResultController,
)
from tests.support.prompt_editor.autocomplete_support import (
    RecordingPromptAutocompleteGateway,
)


from tests.presentation.editor.prompt_editor.autocomplete.phase27_support import (
    _PromptLoraCatalog,
    _lora_item,
)


def test_phase27_lora_results_use_cached_catalog_and_respect_disabled_state() -> None:
    """LoRA autocomplete should consume cached rows only and fail closed when disabled."""

    cached_catalog = _PromptLoraCatalog((_lora_item(),))
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=RecordingPromptAutocompleteGateway({}),
        prompt_lora_catalog_service=cached_catalog,
        limit=10,
    )
    query = PromptLoraAutocompleteQuery(
        query_text="mid",
        token_start=0,
        token_end=9,
        name_start=6,
        name_end=9,
        replacement_start=0,
        replacement_end=9,
        typed_weight_text=None,
        has_closing_bracket=False,
    )

    result = controller.result_for_lora_query(
        query,
        source_identity=None,
        enabled=True,
        thumbnail_cache_available=True,
    )

    assert result.status == "ready"
    assert result.mode == "lora"
    assert cached_catalog.cached_calls == 1
    assert cached_catalog.list_calls == 0
    assert cached_catalog.refresh_calls == 0

    disabled_result = controller.result_for_lora_query(
        query,
        source_identity=None,
        enabled=False,
        thumbnail_cache_available=True,
    )

    assert disabled_result.status == "empty"
    assert cached_catalog.cached_calls == 1
