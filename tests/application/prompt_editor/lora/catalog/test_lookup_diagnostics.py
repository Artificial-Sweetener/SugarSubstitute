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

"""Prompt LoRA lookup diagnostic contracts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from substitute.application.model_metadata import ModelCatalogService
from substitute.application.prompt_editor.lora.catalog import (
    PromptLoraCatalogService,
    _find_lora_in_snapshot,
)
from substitute.application.prompt_editor.lora.diagnostics import (
    lora_prompt_context,
    lora_source_range_context,
)

from tests.application.prompt_editor.lora.catalog.support import (
    _FakeBackend,
    _FakeCatalog,
    _entry,
)


def test_lora_diagnostic_context_normalizes_lookup_fields() -> None:
    """LoRA diagnostic context should expose safe prompt lookup keys."""

    context = lora_prompt_context(r"Folder\Character.safetensors")
    range_context = lora_source_range_context(4, 12)

    assert context == {
        "lora_prompt_name": r"Folder\Character.safetensors",
        "lora_prompt_name_length": len(r"Folder\Character.safetensors"),
        "lora_prompt_name_sha256_12": "e77f9ce2f058",
        "lora_prompt_lookup_key": "folder/character",
        "lora_backend_lookup_key": "folder/character.safetensors",
        "lora_has_path_separator": True,
    }
    assert range_context == {
        "lora_source_start": 4,
        "lora_source_end": 12,
        "lora_source_length": 8,
    }


def test_lora_lookup_diagnostic_reports_match_sources(tmp_path: Path) -> None:
    """LoRA lookup diagnostics should explain which index produced a match."""

    backend = _FakeBackend(
        (
            _entry(r"folder\Character.safetensors", "ABC"),
            _entry(r"other\Solo.safetensors", "DEF"),
        )
    )
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
    )
    model_snapshot = model_catalog.refresh_snapshot("loras")
    service = PromptLoraCatalogService(model_catalog=model_catalog)
    snapshot = service.prepare_snapshot_from_models(
        model_snapshot.items,
        model_generation=model_snapshot.generation,
    )
    backend_only_snapshot = replace(
        snapshot,
        prompt_name_items=MappingProxyType({}),
    )

    prompt_match = _find_lora_in_snapshot(snapshot, r"folder\Character")
    backend_match = _find_lora_in_snapshot(
        backend_only_snapshot,
        r"folder/Character.safetensors",
    )
    bare_match = _find_lora_in_snapshot(snapshot, "Solo")

    assert prompt_match.match_source == "prompt_name"
    assert prompt_match.result is not None
    assert backend_match.match_source == "backend_value"
    assert backend_match.result is not None
    assert bare_match.match_source == "autocomplete_ranked_exact"
    assert bare_match.bare_collision_match_count == 1
    assert bare_match.result is not None


def test_lora_lookup_diagnostic_reports_ranked_duplicate_selection(
    tmp_path: Path,
) -> None:
    """Duplicate bare LoRA names should report ranked fallback selection."""

    backend = _FakeBackend(
        (
            _entry(r"z-last\characters\Ranni.safetensors", "ABC"),
            _entry(r"a-first\characters\Ranni.safetensors", "DEF"),
        )
    )
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
    )
    model_snapshot = model_catalog.refresh_snapshot("loras")
    service = PromptLoraCatalogService(model_catalog=model_catalog)
    snapshot = service.prepare_snapshot_from_models(
        model_snapshot.items,
        model_generation=model_snapshot.generation,
    )

    diagnostic = _find_lora_in_snapshot(snapshot, "Ranni")

    assert diagnostic.match_source == "autocomplete_ranked_exact"
    assert diagnostic.bare_collision_match_count == 2
    assert diagnostic.fallback_candidate_count == 2
    assert diagnostic.selected_fallback_rank == 0
    assert diagnostic.result is not None
    assert diagnostic.result.backend_value == r"a-first\characters\Ranni.safetensors"
