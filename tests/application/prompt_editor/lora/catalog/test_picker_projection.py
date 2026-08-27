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

"""Prompt LoRA picker-projection contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraThumbnailVariant,
)

from tests.application.prompt_editor.lora.catalog.support import (
    _FakeBackend,
    _FakeCatalog,
    _entry,
    _record,
    _service,
)


def test_lora_catalog_inserts_relative_prompt_names_and_tracks_collisions(
    tmp_path: Path,
) -> None:
    """Catalog items should preserve backend path style and flag bare-name collisions."""

    backend = _FakeBackend(
        (
            _entry("Pony\\Concept\\Expressive_H-000001.safetensors", "ABC"),
            _entry("Pony\\Style\\Expressive_H-000001.safetensors", "DEF"),
            _entry("Illustrious/Character/Mineru.safetensors", "GHI"),
        )
    )
    catalog = _FakeCatalog(
        (
            _record(
                value="Pony\\Concept\\Expressive_H-000001.safetensors",
                sha256="ABC",
                model_name="Expressive_H-000001",
                version_name="",
            ),
            _record(
                value="Pony\\Style\\Expressive_H-000001.safetensors",
                sha256="DEF",
                model_name="Expressive_H-000001",
                version_name="",
            ),
            _record(
                value="Illustrious/Character/Mineru.safetensors",
                sha256="GHI",
                model_name="Mineru",
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog)

    items = service.list_loras()

    mineru = next(item for item in items if item.display_name == "Mineru")
    assert mineru.prompt_name == "Illustrious/Character/Mineru"
    assert mineru.thumbnail_variants == (
        PromptLoraThumbnailVariant(
            size=128,
            storage_key="GHI:128",
            width=85,
            height=128,
            content_format="sqthumb-qimage-argb32-premultiplied",
            byte_size=65536,
        ),
    )
    assert "mineru" in mineru.search_text
    assert mineru.display_subtitle == "Version"
    assert mineru.model_page_url == "https://civitai.com/models/1?modelVersionId=2"
    assert mineru.has_collision is False

    collisions = [item for item in items if item.basename == "Expressive_H-000001"]
    assert len(collisions) == 2
    assert {item.prompt_name for item in collisions} == {
        "Pony\\Concept\\Expressive_H-000001",
        "Pony\\Style\\Expressive_H-000001",
    }
    assert all(item.has_collision for item in collisions)
    assert all(item.collision_count == 2 for item in collisions)
    assert all(item.display_subtitle is None for item in collisions)
    assert all(item.model_page_url is not None for item in collisions)
    assert backend.list_model_calls == 1
    assert backend.list_model_refreshes == [False]

    assert service.list_loras() == items
    assert backend.list_model_calls == 1


def test_lora_catalog_keeps_storage_key_thumbnail_variants(
    tmp_path: Path,
) -> None:
    """Cached thumbnail storage keys should pass through without filesystem checks."""

    backend = _FakeBackend((_entry("models/lora.safetensors", "ABC"),))
    catalog = _FakeCatalog(
        (
            _record(
                value="models/lora.safetensors",
                sha256="ABC",
                model_name="Lora",
                storage_key="ABC:128",
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog)

    item = service.list_loras()[0]

    assert item.thumbnail_variants[0].storage_key == "ABC:128"


def test_lora_catalog_keeps_page_name_and_version_names(
    tmp_path: Path,
) -> None:
    """CivitAI page and version names should remain explicit catalog fields."""

    backend = _FakeBackend((_entry("sd15/GesuGao.safetensors", "ABC"),))
    catalog = _FakeCatalog(
        (
            _record(
                value="sd15/GesuGao.safetensors",
                sha256="ABC",
                model_name="Gesugao",
                version_name="v2.0",
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog)

    item = service.list_loras()[0]

    assert item.display_name == "Gesugao"
    assert item.display_subtitle == "v2.0"


def test_lora_catalog_keeps_descriptive_version_name_as_subtitle(
    tmp_path: Path,
) -> None:
    """Hub-style CivitAI pages should keep their page and version labels separate."""

    backend = _FakeBackend(
        (_entry("Pony/Pose/battoujutsu_sword_stance.safetensors", "ABC"),)
    )
    catalog = _FakeCatalog(
        (
            _record(
                value="Pony/Pose/battoujutsu_sword_stance.safetensors",
                sha256="ABC",
                model_name="Sword stances collection [Pony]",
                version_name="Battoujutsu",
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog)

    item = service.list_loras()[0]

    assert item.display_name == "Sword stances collection [Pony]"
    assert item.display_subtitle == "Battoujutsu"
    assert "sword stances" in item.search_text
    assert "battoujutsu" in item.search_text


def test_lora_catalog_keeps_duplicate_page_names_with_version_subtitles(
    tmp_path: Path,
) -> None:
    """Duplicate page names should keep provider version subtitles unchanged."""

    backend = _FakeBackend(
        (
            _entry("SD 1.5/GesuGao.safetensors", "ABC"),
            _entry("SD 1.5/edgGesugao.safetensors", "DEF"),
        )
    )
    catalog = _FakeCatalog(
        (
            _record(
                value="SD 1.5/GesuGao.safetensors",
                sha256="ABC",
                model_name="Gesugao",
                version_name="v1.0",
                model_version_id=1,
            ),
            _record(
                value="SD 1.5/edgGesugao.safetensors",
                sha256="DEF",
                model_name="Gesugao",
                version_name="v2.0",
                model_version_id=2,
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog)

    items = service.list_loras()

    assert {item.display_name for item in items} == {"Gesugao"}
    assert {item.display_subtitle for item in items} == {"v1.0", "v2.0"}
    assert all("gesugao" in item.search_text for item in items)
    assert any("v1.0" in item.search_text for item in items)
    assert any("v2.0" in item.search_text for item in items)
