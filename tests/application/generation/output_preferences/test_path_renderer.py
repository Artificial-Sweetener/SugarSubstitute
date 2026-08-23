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

"""Verify Output path-template rendering and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.generation import (
    OutputPathTemplateError,
    OutputPathTemplateRenderer,
)
from substitute.domain.generation import (
    OutputPreferences,
)


from tests.application.generation.output_preferences.support import (
    build_render_context,
)


def test_renderer_defaults_match_current_output_shape(tmp_path: Path) -> None:
    """Default patterns should render the current dated output path shape."""

    renderer = OutputPathTemplateRenderer()

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern=OutputPreferences().organization.path_pattern,
        context=build_render_context(),
    )

    assert result.path == tmp_path / "2026-05-01" / "007_01_my_workflow_cubea.png"


def test_renderer_resolves_default_run_bucket(tmp_path: Path) -> None:
    """Default run bucket should be the rendered date directory."""

    renderer = OutputPathTemplateRenderer()

    bucket = renderer.resolve_run_bucket(
        output_root=tmp_path,
        path_pattern=OutputPreferences().organization.path_pattern,
        context=build_render_context(),
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
        context=build_render_context(),
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


def test_renderer_uses_job_timestamp_for_date_time_and_day(tmp_path: Path) -> None:
    """Date/time/day tokens should come from the immutable job timestamp."""

    renderer = OutputPathTemplateRenderer()

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern="{day}\\{date}\\{time}_{source}",
        context=build_render_context(),
    )

    assert result.path == tmp_path / "Friday" / "2026-05-01" / "14-32-09_cubea.png"


def test_renderer_supports_seed_token(tmp_path: Path) -> None:
    """The seed token should render from the immutable generation context."""

    renderer = OutputPathTemplateRenderer()

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern="{workflow}\\{seed}_{source}",
        context=build_render_context(seed="1234"),
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
        context=build_render_context(cube_number=2, folder_image_number=13),
    )

    assert result.path == tmp_path / "2026-05-01" / "image_13_02_cubea.png"


def test_renderer_rejects_unknown_tokens(tmp_path: Path) -> None:
    """Unknown template tokens should fail closed."""

    renderer = OutputPathTemplateRenderer()

    with pytest.raises(OutputPathTemplateError, match="Unknown output path token"):
        renderer.render_path(
            output_root=tmp_path,
            path_pattern="{workflow}\\{workflow}_{node_id}",
            context=build_render_context(),
        )


def test_renderer_ignores_accidental_trailing_separator(tmp_path: Path) -> None:
    """A trailing separator should not break an otherwise complete pattern."""

    renderer = OutputPathTemplateRenderer()

    result = renderer.render_path(
        output_root=tmp_path,
        path_pattern="{workflow}\\{run}_{workflow}_{source}\\",
        context=build_render_context(),
    )

    assert result.path == tmp_path / "My Workflow" / "007_my_workflow_cubea.png"


def test_renderer_rejects_relative_roots() -> None:
    """Output roots must be absolute paths."""

    renderer = OutputPathTemplateRenderer()

    with pytest.raises(OutputPathTemplateError, match="absolute"):
        renderer.render_path(
            output_root=Path("relative"),
            path_pattern="{workflow}\\{run}",
            context=build_render_context(),
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
        context=build_render_context(),
    )

    assert result.path == tmp_path / "Bad_Name" / "007_bad_name_source_002.png"
    assert existing.exists()
