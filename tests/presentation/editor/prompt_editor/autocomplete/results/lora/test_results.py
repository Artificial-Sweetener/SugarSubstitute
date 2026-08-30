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

"""Verify LoRA autocomplete result contracts."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.features.autocomplete_result_controller import (
    PromptAutocompleteResultController,
)
from tests.support.prompt_editor.autocomplete_support import (
    build_test_autocomplete_stack,
)
from tests.support.prompt_editor.controller_support import (
    AutocompleteEditorDouble,
    EmptyAutocompleteGateway,
    MenuCursorDouble,
)


from tests.presentation.editor.prompt_editor.autocomplete.results.result_controller_support import (
    _CountingThumbnailAssetRepository,
    _FailingLoraCatalog,
    _Gateway,
    _LoraCatalog,
    _TrackingLoraCatalog,
    _coordinator_lora_item,
    _coordinator_lora_query,
    _lora_item,
    _lora_query,
    _mute_autocomplete_surfaces,
    _refresh_lora_result,
    _thumbnail_variant,
)


def test_coordinator_builds_lora_session_without_tag_gateway() -> None:
    """LoRA autocomplete refresh ranks cached catalog rows through the LoRA path."""

    lora = _coordinator_lora_item()
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_stack(
            AutocompleteEditorDouble(
                MenuCursorDouble(text="<lora:Civ", position=len("<lora:Civ"))
            ),
            prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
            prompt_lora_catalog_service=_LoraCatalog((lora,)),
            lora_thumbnail_cache_available=True,
        )
    )

    _refresh_lora_result(coordinator, _coordinator_lora_query())

    assert coordinator.session_controller.session.mode == "lora"
    assert coordinator.session_controller.session.selected_index == 0
    assert coordinator.session_controller.session.lora_candidates[0].item is lora
    assert (
        coordinator.session_controller.session.lora_candidates[0].replacement_text
        == r"<lora:illustrious\characters\raw_midna:1.00>"
    )


def test_coordinator_uses_cached_loras_without_backend_reads() -> None:
    """LoRA autocomplete does not refresh or cold-load the catalog while typing."""

    lora = _coordinator_lora_item()
    catalog = _TrackingLoraCatalog((lora,))
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_stack(
            AutocompleteEditorDouble(
                MenuCursorDouble(text="<lora:Civ", position=len("<lora:Civ"))
            ),
            prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
            prompt_lora_catalog_service=catalog,
            lora_thumbnail_cache_available=True,
        )
    )
    query = _coordinator_lora_query()

    _refresh_lora_result(coordinator, query)
    _refresh_lora_result(coordinator, query)

    assert catalog.refresh_calls == 0
    assert catalog.list_calls == 0
    assert catalog.cached_calls == 2
    assert coordinator.session_controller.session.mode == "lora"


def test_coordinator_cold_lora_cache_returns_no_candidates() -> None:
    """Cold LoRA autocomplete cache does not block typing with backend reads."""

    catalog = _TrackingLoraCatalog(None)
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_stack(
            AutocompleteEditorDouble(
                MenuCursorDouble(text="<lora:Civ", position=len("<lora:Civ"))
            ),
            prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
            prompt_lora_catalog_service=catalog,
            lora_thumbnail_cache_available=True,
        )
    )

    _refresh_lora_result(coordinator, _coordinator_lora_query())

    assert catalog.refresh_calls == 0
    assert catalog.list_calls == 0
    assert catalog.cached_calls == 1
    assert coordinator.session_controller.session.mode == "none"
    assert coordinator.session_controller.session.lora_candidates == ()


def test_coordinator_lora_refresh_does_not_load_thumbnail_assets() -> None:
    """LoRA autocomplete refresh does not decode thumbnail assets while typing."""

    asset_repository = _CountingThumbnailAssetRepository()
    items = tuple(
        _coordinator_lora_item(
            display_name=f"CivitAI LoRA {index:03}",
            basename=f"lora_{index:03}",
            prompt_name=rf"illustrious\characters\lora_{index:03}",
            thumbnail_variants=(_thumbnail_variant(f"lora_{index:03}:128"),),
        )
        for index in range(200)
    )
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_stack(
            AutocompleteEditorDouble(MenuCursorDouble(text="<lora:Civ", position=9)),
            prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
            prompt_lora_catalog_service=_LoraCatalog(items),
            lora_thumbnail_cache_available=True,
        )
    )

    _refresh_lora_result(coordinator, _coordinator_lora_query())

    assert len(coordinator.session_controller.session.lora_candidates) == 200
    assert asset_repository.reads == 0


def test_lora_results_use_cached_catalog_and_fail_closed() -> None:
    """LoRA result preparation consumes cached rows only and returns safe empty/error states."""

    catalog = _LoraCatalog((_lora_item(),))
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=_Gateway({}),
        prompt_lora_catalog_service=catalog,
        limit=10,
    )

    ready = controller.result_for_lora_query(
        _lora_query(),
        source_identity=None,
        enabled=True,
        thumbnail_cache_available=True,
    )
    disabled = controller.result_for_lora_query(
        _lora_query(),
        source_identity=None,
        enabled=False,
        thumbnail_cache_available=True,
    )
    no_thumbnail = controller.result_for_lora_query(
        _lora_query(),
        source_identity=None,
        enabled=True,
        thumbnail_cache_available=False,
    )
    failing = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=_Gateway({}),
        prompt_lora_catalog_service=_FailingLoraCatalog(),
        limit=10,
    ).result_for_lora_query(
        _lora_query(),
        source_identity=None,
        enabled=True,
        thumbnail_cache_available=True,
    )

    assert ready.status == "ready"
    assert ready.mode == "lora"
    assert ready.lora_candidates
    assert catalog.cached_calls == 1
    assert catalog.list_calls == 0
    assert catalog.refresh_calls == 0
    assert disabled.status == "empty"
    assert no_thumbnail.status == "empty"
    assert failing.status == "error"
    assert failing.error_reason == "lora_catalog_cache_error"
