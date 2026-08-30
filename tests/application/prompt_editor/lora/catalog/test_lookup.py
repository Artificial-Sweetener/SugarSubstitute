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

"""Prompt LoRA catalog lookup contracts."""

from __future__ import annotations

from pathlib import Path

from tests.application.prompt_editor.lora.catalog.support import (
    _FakeBackend,
    _FakeCatalog,
    _entry,
    _service,
)


def test_lora_catalog_resolves_unique_bare_prompt_name_to_nested_item(
    tmp_path: Path,
) -> None:
    """Pasted bare LoRA names should resolve after the catalog is passively loaded."""

    backend = _FakeBackend(
        (
            _entry(
                r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1.safetensors",
                "ABC",
            ),
        )
    )
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
    )

    service.list_loras()
    item = service.find_lora("Ranni_illusXLNoobAI_Incrs_v1")

    assert item is not None
    assert item.prompt_name == r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1"


def test_lora_catalog_repairs_stale_prompt_path_by_unique_basename(
    tmp_path: Path,
) -> None:
    """Wrong restored LoRA folders should repair when the basename is unique."""

    backend = _FakeBackend(
        (_entry(r"NoobAI\Bridge Tools Line Weight.safetensors", "ABC"),)
    )
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
    )

    service.list_loras()
    diagnostic = service.lookup_lora(r"ILLUSTRIOUS\CONCEPTS\Bridge Tools Line Weight")

    assert diagnostic.match_source == "autocomplete_ranked_basename"
    assert diagnostic.result is not None
    assert diagnostic.result.backend_value == (
        r"NoobAI\Bridge Tools Line Weight.safetensors"
    )


def test_lora_catalog_find_lora_does_not_require_backend_refresh(
    tmp_path: Path,
) -> None:
    """Loaded LoRA lookup should not require a fresh Backend refresh."""

    backend = _FakeBackend(
        (_entry(r"illustrious\characters\Ranni.safetensors", "ABC"),),
        fail_refresh=True,
    )
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
    )

    service.list_loras()
    item = service.find_lora("Ranni")

    assert item is not None
    assert item.prompt_name == r"illustrious\characters\Ranni"
    assert backend.list_model_calls == 1
    assert backend.list_model_refreshes == [False]


def test_lora_catalog_uses_first_ranked_duplicate_bare_prompt_name(
    tmp_path: Path,
) -> None:
    """Duplicate pasted bare LoRA names should pick autocomplete's first candidate."""

    backend = _FakeBackend(
        (
            _entry(r"z-last\characters\Ranni.safetensors", "ABC"),
            _entry(r"a-first\characters\Ranni.safetensors", "DEF"),
        )
    )
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
    )

    service.list_loras()
    diagnostic = service.lookup_lora("Ranni")

    assert diagnostic.match_source == "autocomplete_ranked_exact"
    assert diagnostic.fallback_candidate_count == 2
    assert diagnostic.selected_fallback_rank == 0
    assert diagnostic.result is not None
    assert diagnostic.result.backend_value == r"a-first\characters\Ranni.safetensors"
    assert service.find_lora(r"z-last\characters\Ranni") is not None


def test_lora_catalog_uses_indexed_backend_value_matches(
    tmp_path: Path,
) -> None:
    """Indexed lookup should preserve extension and backend path matching behavior."""

    backend = _FakeBackend((_entry(r"folder\Character.safetensors", "ABC"),))
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
    )

    service.list_loras()

    assert service.find_lora(r"folder\Character") is not None
    assert service.find_lora(r"folder/Character.safetensors") is not None
    assert backend.list_model_calls == 1
