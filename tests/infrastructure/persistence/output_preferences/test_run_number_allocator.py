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

"""Contract tests for filesystem generation output run-number allocation."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.generation import OutputRunBucket
from substitute.infrastructure.persistence.image_naming import (
    get_next_folder_image_number,
)
from substitute.infrastructure.persistence.output_run_number_allocator import (
    FileOutputRunNumberAllocator,
)


def _bucket(directory: Path, label: str = "bucket") -> OutputRunBucket:
    """Return a deterministic output bucket for allocator tests."""

    return OutputRunBucket(
        key=str(directory).replace("\\", "/").casefold(),
        directory=directory,
        display_label=label,
    )


def test_output_run_number_allocator_starts_at_one_without_files(
    tmp_path: Path,
) -> None:
    """Allocator should return one for a bucket with no saved runs."""

    allocator = FileOutputRunNumberAllocator()

    assert allocator.allocate_output_run_number(bucket=_bucket(tmp_path)) == 1


def test_output_run_number_allocator_uses_default_pattern_saved_file_maximum(
    tmp_path: Path,
) -> None:
    """Existing default-pattern files should raise the next allocated number."""

    output_dir = tmp_path / "2026-05-12"
    output_dir.mkdir()
    (output_dir / "001_01_recipe_cubea.png").write_text("", encoding="utf-8")
    (output_dir / "005_02_recipe_cubeb.png").write_text("", encoding="utf-8")
    other_dir = tmp_path / "2026-05-11"
    other_dir.mkdir()
    (other_dir / "910_recipe_cubea.png").write_text("", encoding="utf-8")
    allocator = FileOutputRunNumberAllocator()

    assert allocator.allocate_output_run_number(bucket=_bucket(output_dir)) == 6


def test_output_run_number_allocator_ignores_nested_default_pattern_files(
    tmp_path: Path,
) -> None:
    """Default-pattern bucket scans should not read numbers from nested folders."""

    output_dir = tmp_path / "2026-05-12"
    nested = output_dir / "nested"
    nested.mkdir(parents=True)
    (nested / "009_recipe_cubea.png").write_text("", encoding="utf-8")
    allocator = FileOutputRunNumberAllocator()

    assert allocator.allocate_output_run_number(bucket=_bucket(output_dir)) == 1


def test_output_run_number_allocator_uses_directory_run_component(
    tmp_path: Path,
) -> None:
    """Patterns with `{run}` in a directory component should prevent collisions."""

    workflow_bucket = tmp_path / "untitled_recipe"
    (workflow_bucket / "001").mkdir(parents=True)
    (workflow_bucket / "001" / "text_to_image.png").write_text("", encoding="utf-8")
    (workflow_bucket / "004").mkdir()
    (workflow_bucket / "004" / "diffusion_upscale.png").write_text(
        "",
        encoding="utf-8",
    )
    allocator = FileOutputRunNumberAllocator(path_pattern="{workflow}\\{run}\\{source}")

    assert allocator.allocate_output_run_number(bucket=_bucket(workflow_bucket)) == 5


def test_output_run_number_allocator_keeps_buckets_independent(
    tmp_path: Path,
) -> None:
    """Filesystem maxima should be scoped by output bucket."""

    other_bucket = tmp_path / "2026-05-11"
    current_bucket = tmp_path / "2026-05-12"
    other_bucket.mkdir()
    current_bucket.mkdir()
    (other_bucket / "007_recipe_cubea.png").write_text("", encoding="utf-8")
    allocator = FileOutputRunNumberAllocator()

    assert allocator.allocate_output_run_number(bucket=_bucket(current_bucket)) == 1


def test_folder_image_number_allocator_uses_matching_filename_maximum(
    tmp_path: Path,
) -> None:
    """Folder image numbers should increment across matching images in one folder."""

    (tmp_path / "image_01_cubea.png").write_text("", encoding="utf-8")
    (tmp_path / "image_03_cubeb.png").write_text("", encoding="utf-8")
    (tmp_path / "unrelated_99.png").write_text("", encoding="utf-8")

    assert get_next_folder_image_number(str(tmp_path), "Image {image#}_{source}") == 4


def test_folder_image_number_allocator_reserves_numbers_in_process(
    tmp_path: Path,
) -> None:
    """Consecutive allocations should not reuse a number before files appear."""

    pattern = "Image {image#}_{source}"

    first = get_next_folder_image_number(str(tmp_path), pattern)
    second = get_next_folder_image_number(str(tmp_path), pattern)

    assert (first, second) == (1, 2)
