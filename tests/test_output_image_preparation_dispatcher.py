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

"""Contract tests for asynchronous output image preparation helpers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage

from substitute.presentation.shell.output_image_commit_pipeline import (
    FailedOutputImagePreparation,
    OutputImageCommitRequest,
    PreparedOutputImage,
)
from substitute.presentation.shell.output_image_preparation_dispatcher import (
    prepare_output_image,
)


class _Loader:
    def __init__(self, image: QImage | None) -> None:
        self.image = image
        self.paths: list[Path] = []

    def load_output_image(self, path: Path) -> QImage | None:
        self.paths.append(path)
        return self.image


def test_prepare_output_image_returns_detached_image() -> None:
    """Output preparation should detach decoded image data before delivery."""

    image = QImage(32, 16, QImage.Format.Format_ARGB32)
    image.fill(1)
    request = _request(Path("E:/out.png"))

    result = prepare_output_image(request, loader=_Loader(image))

    assert isinstance(result, PreparedOutputImage)
    assert result.image.width() == 32
    assert result.image.height() == 16
    assert result.image.cacheKey() != image.cacheKey()


def test_prepare_output_image_keeps_large_images_full_resolution() -> None:
    """Large outputs should stay full resolution for QPane pyramid handling."""

    image = QImage(4096, 1024, QImage.Format.Format_ARGB32)
    image.fill(1)

    result = prepare_output_image(
        _request(Path("E:/large.png")),
        loader=_Loader(image),
    )

    assert isinstance(result, PreparedOutputImage)
    assert result.image.width() == 4096
    assert result.image.height() == 1024
    assert result.image.cacheKey() != image.cacheKey()


def test_prepare_output_image_converts_null_load_to_failure() -> None:
    """Null decode results should become failure DTOs instead of exceptions."""

    result = prepare_output_image(
        _request(Path("E:/missing.png")),
        loader=_Loader(None),
    )

    assert isinstance(result, FailedOutputImagePreparation)
    assert result.request.file_path == Path("E:/missing.png")


def _request(path: Path) -> OutputImageCommitRequest:
    """Return a minimal output commit request for preparation tests."""

    return OutputImageCommitRequest(
        workflow_id="wf",
        file_path=path,
        node_id="save",
        node_meta_title="Cube.Output",
        workflow_name="Workflow",
        source_key="wf:save",
        source_label="Save",
    )
