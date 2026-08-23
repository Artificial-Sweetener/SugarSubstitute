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

"""Verify generation preview preference repository behavior."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.domain.generation import (
    GenerationPreviewMethod,
    default_generation_preview_preferences,
)
from substitute.infrastructure.persistence import (
    FileGenerationPreviewPreferenceRepository,
)


def test_file_generation_preview_repository_round_trips_preferences(
    tmp_path: Path,
) -> None:
    """Persist and restore a selected preview method."""

    repository = FileGenerationPreviewPreferenceRepository(tmp_path)
    repository.save(
        default_generation_preview_preferences().with_method(
            GenerationPreviewMethod.TAESD
        )
    )

    loaded = repository.load()

    assert loaded.enabled is True
    assert loaded.method is GenerationPreviewMethod.TAESD


def test_file_generation_preview_repository_defaults_missing_file(
    tmp_path: Path,
) -> None:
    """Return domain defaults when no preference file exists."""

    assert FileGenerationPreviewPreferenceRepository(tmp_path).load() == (
        default_generation_preview_preferences()
    )


def test_file_generation_preview_repository_defaults_unknown_method(
    tmp_path: Path,
) -> None:
    """Fall back to latent RGB when persisted method text is unknown."""

    (tmp_path / "generation_preview.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "enabled": False,
                "method": "unknown",
            }
        ),
        encoding="utf-8",
    )

    loaded = FileGenerationPreviewPreferenceRepository(tmp_path).load()

    assert loaded.enabled is False
    assert loaded.method is GenerationPreviewMethod.LATENT2RGB
