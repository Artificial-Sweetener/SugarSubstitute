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

"""Verify canonical and derivative final-image encoding."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image

from substitute.application.generation import (
    JpegOutputSettings,
    JpegSizingMode,
)
from substitute.application.ports import OutputSavePlan
from substitute.infrastructure.comfy.output_image_persistence import (
    OutputImagePersistence,
)
from tests.infrastructure.comfy.output_images.support import (
    build_png_bytes,
    build_source_identity,
)


def test_canonical_png_keeps_recipe_and_optional_jpeg_is_same_stem(
    tmp_path: Path,
) -> None:
    """JPEG is an additional derivative; the PNG remains recipe-bearing."""

    persistence = OutputImagePersistence(
        output_save_plan=OutputSavePlan(
            output_root=tmp_path,
            path_pattern="{workflow}_{source}",
            workflow_name="My Workflow",
            output_run_number=1,
            job_started_at=datetime(2026, 7, 18),
            jpeg=JpegOutputSettings(enabled=True, quality=82),
        ),
        workflow_payload={"workflow": {"nodes": [{"id": 1}]}},
        sugar_script="use cube as Main",
        cube_numbers_by_alias={},
    )

    result = persistence.persist_output_image(
        image_bytes=build_png_bytes(),
        source_identity=build_source_identity("Main"),
    )

    assert result.file_path is not None
    jpeg_path = result.file_path.with_suffix(".jpg")
    assert result.file_path.is_file()
    assert jpeg_path.is_file()
    with Image.open(result.file_path) as png:
        assert png.info["sugar_script"].endswith("use cube as Main")
        assert "workflow" in png.info
    with Image.open(jpeg_path) as jpeg:
        assert jpeg.format == "JPEG"
        assert jpeg.size == (64, 48)


def test_target_size_jpeg_encoder_produces_bounded_derivative(
    tmp_path: Path,
) -> None:
    """Target-size mode should search quality without changing the canonical PNG."""

    persistence = OutputImagePersistence(
        output_save_plan=OutputSavePlan(
            output_root=tmp_path,
            path_pattern="target",
            workflow_name="Workflow",
            output_run_number=1,
            job_started_at=datetime(2026, 7, 18),
            jpeg=JpegOutputSettings(
                enabled=True,
                sizing_mode=JpegSizingMode.TARGET_SIZE,
                target_size_kib=4,
            ),
        ),
        workflow_payload={},
        sugar_script="recipe",
        cube_numbers_by_alias={},
    )

    result = persistence.persist_output_image(
        image_bytes=build_png_bytes(width=256, height=256),
        source_identity=build_source_identity("Main"),
    )

    assert result.file_path is not None
    assert result.file_path.with_suffix(".jpg").stat().st_size <= 4 * 1024
    with Image.open(result.file_path) as png:
        assert png.size == (256, 256)
