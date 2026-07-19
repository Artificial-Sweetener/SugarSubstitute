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

"""Contract tests for output organization preferences and path rendering."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from substitute.application.generation import (
    OutputPreferenceService,
    OutputPathTemplateError,
    OutputPathTemplateRenderer,
)
from substitute.domain.generation import (
    OutputOrganizationSettings,
    OutputPreferences,
    OutputPathRenderContext,
)
from substitute.infrastructure.persistence import (
    FileOutputPreferenceRepository,
)


class _MemoryOutputRepository:
    """Persist output organization preferences in memory."""

    def __init__(self) -> None:
        """Create repository with default preferences."""

        self.preferences = OutputPreferences()

    def load(self) -> OutputPreferences:
        """Return stored preferences."""

        return self.preferences

    def save(self, preferences: OutputPreferences) -> None:
        """Store preferences in memory."""

        self.preferences = preferences


def test_renderer_defaults_match_current_output_shape(tmp_path: Path) -> None:
    """Default patterns should render the current dated output path shape."""

    renderer = OutputPathTemplateRenderer()

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern=OutputPreferences().organization.path_pattern,
        context=_context(),
    )

    assert result.path == tmp_path / "2026-05-01" / "007_01_my_workflow_cubea.png"


def test_renderer_resolves_default_run_bucket(tmp_path: Path) -> None:
    """Default run bucket should be the rendered date directory."""

    renderer = OutputPathTemplateRenderer()

    bucket = renderer.resolve_run_bucket(
        output_root=tmp_path,
        path_pattern=OutputPreferences().organization.path_pattern,
        context=_context(),
    )

    assert bucket.directory == tmp_path / "2026-05-01"
    assert bucket.display_label == "2026-05-01"
    assert bucket.key == str(bucket.directory).replace("\\", "/").casefold()


def test_renderer_resolves_bucket_before_run_directory(tmp_path: Path) -> None:
    """Run tokens in directory components should not become part of the bucket."""

    renderer = OutputPathTemplateRenderer()

    bucket = renderer.resolve_run_bucket(
        output_root=tmp_path,
        path_pattern="{workflow}\\{run}\\{source}",
        context=_context(),
    )

    assert bucket.directory == tmp_path / "My Workflow"
    assert bucket.display_label == "My Workflow"


def test_renderer_reports_bucket_affecting_time_tokens() -> None:
    """Projection keys should include only time tokens that shape run buckets."""

    renderer = OutputPathTemplateRenderer()

    assert renderer.bucket_affecting_time_tokens("{date}\\{run}_{source}") == ("date",)
    assert renderer.bucket_affecting_time_tokens("{workflow}\\{time}\\{run}") == (
        "time",
    )
    assert (
        renderer.bucket_affecting_time_tokens(
            "{workflow}\\{run}\\{date}_{time}_{source}"
        )
        == ()
    )
    assert (
        renderer.bucket_affecting_time_tokens(
            "{workflow}\\{run}_{date}_{time}_{source}"
        )
        == ()
    )


def test_service_projection_cache_key_tracks_bucket_affecting_time(
    tmp_path: Path,
) -> None:
    """Output projection keys should change only for bucket-shaping time tokens."""

    repository = _MemoryOutputRepository()
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


def test_renderer_uses_job_timestamp_for_date_time_and_day(tmp_path: Path) -> None:
    """Date/time/day tokens should come from the immutable job timestamp."""

    renderer = OutputPathTemplateRenderer()

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern="{day}\\{date}\\{time}_{source}",
        context=_context(),
    )

    assert result.path == tmp_path / "Friday" / "2026-05-01" / "14-32-09_cubea.png"


def test_renderer_supports_seed_token(tmp_path: Path) -> None:
    """The seed token should render from the immutable generation context."""

    renderer = OutputPathTemplateRenderer()

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern="{workflow}\\{seed}_{source}",
        context=_context(seed="1234"),
    )

    assert result.path == tmp_path / "My Workflow" / "1234_cubea.png"


def test_renderer_supports_cube_and_folder_image_number_tokens(
    tmp_path: Path,
) -> None:
    """Cube and folder-wide image ordinal tokens should render zero-padded values."""

    renderer = OutputPathTemplateRenderer()

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern="{date}\\Image {image#}_{cube#}_{source}",
        context=_context(cube_number=2, folder_image_number=13),
    )

    assert result.path == tmp_path / "2026-05-01" / "image_13_02_cubea.png"


def test_service_preview_renders_example_seed(tmp_path: Path) -> None:
    """Settings previews should show a deterministic example seed token."""

    repository = _MemoryOutputRepository()
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


def test_renderer_rejects_unknown_tokens(tmp_path: Path) -> None:
    """Unknown template tokens should fail closed."""

    renderer = OutputPathTemplateRenderer()

    with pytest.raises(OutputPathTemplateError, match="Unknown output path token"):
        renderer.render_path(
            output_root=tmp_path,
            path_pattern="{workflow}\\{workflow}_{node_id}",
            context=_context(),
        )


def test_renderer_ignores_accidental_trailing_separator(tmp_path: Path) -> None:
    """A trailing separator should not break an otherwise complete pattern."""

    renderer = OutputPathTemplateRenderer()

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern="{workflow}\\{run}_{workflow}_{source}\\",
        context=_context(),
    )

    assert result.path == tmp_path / "My Workflow" / "007_my_workflow_cubea.png"


def test_renderer_rejects_relative_roots() -> None:
    """Output roots must be absolute paths."""

    renderer = OutputPathTemplateRenderer()

    with pytest.raises(OutputPathTemplateError, match="absolute"):
        renderer.render_path(
            output_root=Path("relative"),
            path_pattern="{workflow}\\{run}",
            context=_context(),
        )


def test_renderer_sanitizes_components_and_prevents_overwrite(
    tmp_path: Path,
) -> None:
    """Rendered paths should be safe and collisions should get numbered suffixes."""

    renderer = OutputPathTemplateRenderer()
    existing = tmp_path / "Bad_Name" / "007_bad_name_source.png"
    existing.parent.mkdir()
    existing.write_text("", encoding="utf-8")

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern="Bad:Name\\{run}_Bad:Name_Source",
        context=_context(),
    )

    assert result.path == tmp_path / "Bad_Name" / "007_bad_name_source_002.png"
    assert existing.exists()


def test_service_save_rejects_invalid_pattern_without_persisting(
    tmp_path: Path,
) -> None:
    """Preference service should not save invalid token patterns."""

    repository = _MemoryOutputRepository()
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


def test_jpeg_quality_defaults_to_100_without_overwriting_persisted_values(
    tmp_path: Path,
) -> None:
    """Missing quality should use 100 while an explicit older value remains intact."""

    preferences_path = tmp_path / "output_organization.json"
    preferences_path.write_text(
        json.dumps({"schema_version": "2", "jpeg": {"enabled": True}}),
        encoding="utf-8",
    )

    assert FileOutputPreferenceRepository(tmp_path).load().jpeg.quality == 100

    preferences_path.write_text(
        json.dumps(
            {
                "schema_version": "2",
                "jpeg": {"enabled": True, "quality": 90},
            }
        ),
        encoding="utf-8",
    )

    assert FileOutputPreferenceRepository(tmp_path).load().jpeg.quality == 90


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


def _context(
    *,
    seed: str = "",
    cube_number: int | None = 1,
    folder_image_number: int | None = 1,
) -> OutputPathRenderContext:
    """Return a representative render context."""

    return OutputPathRenderContext(
        workflow_name="My Workflow",
        source="CubeA",
        cube="CubeA",
        output_run_number=7,
        cube_number=cube_number,
        folder_image_number=folder_image_number,
        job_started_at=datetime(2026, 5, 1, 14, 32, 9),
        width=1024,
        height=1024,
        index=1,
        set_index=1,
        seed=seed,
    )
