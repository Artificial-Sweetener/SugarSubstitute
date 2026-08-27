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

"""Verify Output preference service projection and validation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


from substitute.application.generation import (
    OutputPreferenceService,
)
from substitute.domain.generation import (
    OutputOrganizationSettings,
    OutputPreferences,
)


from tests.application.generation.output_preferences.support import (
    MemoryOutputRepository,
)


def test_service_projection_cache_key_tracks_bucket_affecting_time(
    tmp_path: Path,
) -> None:
    """Output projection keys should change only for bucket-shaping time tokens."""

    repository = MemoryOutputRepository()
    service = OutputPreferenceService(
        repository,
        default_output_root=tmp_path,
    )
    repository.preferences = OutputPreferences(
        organization=OutputOrganizationSettings(
            path_pattern="{date}\\{run}_{time}_{source}"
        ),
    )

    first = service.output_run_projection_cache_key(now=datetime(2026, 5, 1, 14, 32, 9))
    second = service.output_run_projection_cache_key(
        now=datetime(2026, 5, 1, 14, 33, 10)
    )
    third = service.output_run_projection_cache_key(now=datetime(2026, 5, 2, 14, 32, 9))

    assert first == second
    assert first != third

    repository.preferences = OutputPreferences(
        organization=OutputOrganizationSettings(
            path_pattern="{workflow}\\{run}_{time}_{source}"
        ),
    )
    filename_time_first = service.output_run_projection_cache_key(
        now=datetime(2026, 5, 1, 14, 32, 9)
    )
    filename_time_second = service.output_run_projection_cache_key(
        now=datetime(2026, 5, 1, 14, 33, 10)
    )

    assert filename_time_first == filename_time_second


def test_service_preview_renders_example_seed(tmp_path: Path) -> None:
    """Settings previews should show a deterministic example seed token."""

    repository = MemoryOutputRepository()
    service = OutputPreferenceService(
        repository,
        default_output_root=tmp_path,
    )

    preview = service.render_preview(
        OutputPreferences(
            organization=OutputOrganizationSettings(
                path_pattern="{workflow}\\{seed}_{source}"
            )
        )
    )

    assert preview.path == tmp_path / "My Workflow" / "123456789_main_output.png"


def test_service_save_rejects_invalid_pattern_without_persisting(
    tmp_path: Path,
) -> None:
    """Preference service should not save invalid token patterns."""

    repository = MemoryOutputRepository()
    service = OutputPreferenceService(
        repository,
        default_output_root=tmp_path,
    )

    result = service.save_preferences(
        OutputPreferences(
            organization=OutputOrganizationSettings(path_pattern="{node_id}")
        )
    )

    assert result.succeeded is False
    assert (
        repository.preferences.organization.path_pattern
        == "{date}\\{run}_{cube#}_{workflow}_{source}"
    )
