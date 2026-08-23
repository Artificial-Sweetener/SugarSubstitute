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

"""Verify file-backed Output preference compatibility and recovery."""

from __future__ import annotations

import json
from pathlib import Path


from substitute.domain.generation import (
    OutputOrganizationSettings,
    OutputPreferences,
    OutputTransferFormat,
    OutputTransferSettings,
)
from substitute.infrastructure.persistence import (
    FileOutputPreferenceRepository,
)


def test_file_repository_round_trips_output_preferences(tmp_path: Path) -> None:
    """JSON repository should persist output organization preferences."""

    repository = FileOutputPreferenceRepository(tmp_path)
    preferences = OutputPreferences(
        organization=OutputOrganizationSettings(
            output_root=Path("D:/Images"),
            path_pattern="{workflow}\\{date}\\{run}_{source}",
        ),
    )

    repository.save(preferences)
    loaded = repository.load()

    assert loaded.organization.output_root == Path("D:/Images")
    assert loaded.organization.path_pattern == "{workflow}\\{date}\\{run}_{source}"


def test_file_repository_returns_defaults_for_invalid_json(tmp_path: Path) -> None:
    """Invalid persisted JSON should not crash preference loading."""

    (tmp_path / "output_organization.json").write_text("{", encoding="utf-8")

    loaded = FileOutputPreferenceRepository(tmp_path).load()

    assert loaded == OutputPreferences()


def test_file_repository_defaults_legacy_preferences_to_png_transfer(
    tmp_path: Path,
) -> None:
    """Preferences written before transfer support should preserve PNG transfer."""

    (tmp_path / "output_organization.json").write_text(
        json.dumps({"schema_version": "2", "jpeg": {"enabled": True}}),
        encoding="utf-8",
    )

    loaded = FileOutputPreferenceRepository(tmp_path).load()

    assert loaded.transfer.preferred_format is OutputTransferFormat.CANONICAL_PNG


def test_file_repository_round_trips_preferred_transfer_format(tmp_path: Path) -> None:
    """The separate transfer choice should persist independently of JPEG settings."""

    repository = FileOutputPreferenceRepository(tmp_path)
    repository.save(
        OutputPreferences(
            transfer=OutputTransferSettings(
                preferred_format=OutputTransferFormat.COMPANION_JPEG
            )
        )
    )

    loaded = repository.load()

    assert loaded.transfer.preferred_format is OutputTransferFormat.COMPANION_JPEG


def test_file_repository_preserves_null_output_root(tmp_path: Path) -> None:
    """A null output root should preserve default-root semantics."""

    payload = {
        "schema_version": "1",
        "output_root": None,
        "path_pattern": "{workflow}\\{run}_{source}",
    }
    (tmp_path / "output_organization.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    loaded = FileOutputPreferenceRepository(tmp_path).load()

    assert loaded.organization.output_root is None
    assert loaded.organization.path_pattern == "{workflow}\\{run}_{source}"
