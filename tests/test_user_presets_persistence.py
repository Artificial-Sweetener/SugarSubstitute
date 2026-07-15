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

"""Contract tests for user preset JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.domain.user_presets import (
    DimensionPresetPayload,
    GLOBAL_PRESET_ASSOCIATION,
    UserPreset,
    UserPresetKind,
)
from substitute.infrastructure.persistence import JsonUserPresetRepository


def test_missing_user_presets_file_returns_empty_tuple(tmp_path: Path) -> None:
    """A missing user preset file should behave like an empty collection."""

    repository = JsonUserPresetRepository(tmp_path / "user")

    assert repository.load_presets() == ()


def test_save_creates_parent_and_writes_versioned_document(tmp_path: Path) -> None:
    """Saving presets should create user storage and write schema version one."""

    repository = JsonUserPresetRepository(tmp_path / "user")
    preset = _preset()

    repository.save_presets((preset,))

    payload = json.loads(repository.preset_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert repository.load_presets() == (preset,)


def test_invalid_json_logs_and_returns_empty_tuple(tmp_path: Path) -> None:
    """Damaged user preset JSON should not raise or delete existing data."""

    repository = JsonUserPresetRepository(tmp_path / "user")
    repository.preset_path.parent.mkdir(parents=True)
    repository.preset_path.write_text("{", encoding="utf-8")

    assert repository.load_presets() == ()
    assert repository.preset_path.read_text(encoding="utf-8") == "{"


def test_non_object_json_returns_empty_tuple(tmp_path: Path) -> None:
    """A valid but unsupported JSON root should decode as no presets."""

    repository = JsonUserPresetRepository(tmp_path / "user")
    repository.preset_path.parent.mkdir(parents=True)
    repository.preset_path.write_text("[]", encoding="utf-8")

    assert repository.load_presets() == ()


def _preset() -> UserPreset:
    """Return one deterministic user preset for repository tests."""

    return UserPreset(
        id="dimension:test",
        kind=UserPresetKind.DIMENSION,
        label="1024 x 1536",
        payload=DimensionPresetPayload(short_edge=1024, long_edge=1536),
        associations=(GLOBAL_PRESET_ASSOCIATION,),
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )
