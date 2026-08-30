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

"""Test model-catalog row projection behavior."""

from __future__ import annotations

from pathlib import Path

from substitute.application.model_metadata import (
    ModelCatalogService,
    ModelThumbnailVariant,
)
from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailVariant,
)

from .support import _FakeBackend, _FakeCatalog, _entry, _record


def test_model_catalog_preserves_thumbnail_variants_without_file_checks(
    tmp_path: Path,
) -> None:
    """Thumbnail storage references should pass through all roles deterministically."""

    backend = _FakeBackend((_entry("checkpoints", "model.safetensors", "ABC"),))
    catalog = _FakeCatalog(
        (
            _record(
                kind="checkpoints",
                value="model.safetensors",
                sha256="ABC",
                model_name="Model",
                variants=(
                    ThumbnailVariant(
                        size=768,
                        storage_key="model:banner",
                        width=768,
                        height=160,
                        content_format="sqthumb-qimage-argb32-premultiplied",
                        byte_size=491520,
                        role=BANNER_THUMBNAIL_ROLE,
                    ),
                    ThumbnailVariant(
                        size=128,
                        storage_key="model:standard",
                        width=85,
                        height=128,
                        content_format="sqthumb-qimage-argb32-premultiplied",
                        byte_size=43520,
                        role=STANDARD_THUMBNAIL_ROLE,
                    ),
                ),
            ),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=catalog,
    )

    item = service.list_models("checkpoints")[0]

    assert item.thumbnail_variants == (
        ModelThumbnailVariant(
            size=768,
            storage_key="model:banner",
            width=768,
            height=160,
            content_format="sqthumb-qimage-argb32-premultiplied",
            byte_size=491520,
            role=BANNER_THUMBNAIL_ROLE,
        ),
        ModelThumbnailVariant(
            size=128,
            storage_key="model:standard",
            width=85,
            height=128,
            content_format="sqthumb-qimage-argb32-premultiplied",
            byte_size=43520,
            role=STANDARD_THUMBNAIL_ROLE,
        ),
    )


def test_model_catalog_sorts_and_flags_basename_collisions(tmp_path: Path) -> None:
    """Catalog output should be deterministic and report duplicate bare names."""

    backend = _FakeBackend(
        (
            _entry("checkpoints", "z/model.safetensors", "AAA", display_name="Zulu"),
            _entry("checkpoints", "a/model.safetensors", "BBB", display_name="Alpha"),
            _entry("checkpoints", "m/other.safetensors", "CCC", display_name="Middle"),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
    )

    items = service.list_models("checkpoints")

    assert [item.display_name for item in items] == ["Alpha", "Middle", "Zulu"]
    model_items = [item for item in items if item.basename == "model"]
    assert len(model_items) == 2
    assert all(item.has_collision for item in model_items)
    assert all(item.collision_count == 2 for item in model_items)
