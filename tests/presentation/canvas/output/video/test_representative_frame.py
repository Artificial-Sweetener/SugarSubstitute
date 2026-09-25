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

"""Verify paused video frames replace CuteCanvas pixels under stable identity."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtGui import QColor
from cutecanvas import ExecutionRuntime

from substitute.application.ports.video import VideoRepresentativeFrame
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_video_representative_frame import (
    OutputVideoRepresentativeFramePresenter,
)
from tests.presentation.canvas.output.document.rendering_support import (
    _wait_for_rendered_color,
)
from tests.presentation.canvas.output.document.support import _app, _image
from tests.support.qt.lifecycle import destroy_qt_object


def test_paused_frame_replaces_visible_tile_without_replacing_composition(
    execution_runtime: ExecutionRuntime,
    tmp_path: Path,
) -> None:
    """Keep navigation identity and artifact path while updating rendered pixels."""

    app = _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    media_id = uuid4()
    video_path = tmp_path / "clip.webm"
    video_path.write_bytes(b"video")
    try:
        assert document.admit_image(media_id, _image("blue"), path=video_path)
        composition_id = document.composition_id_for(media_id)
        assert composition_id is not None
        assert document.present_grid((media_id,))
        target = document.workspace.canvasFor(composition_id)
        assert target is not None
        document.workspace.resize(320, 240)
        document.workspace.show()
        app.processEvents()
        assert _wait_for_rendered_color(app, target, QColor("blue"))

        frame = VideoRepresentativeFrame(
            time_seconds=1.25,
            width=2,
            height=1,
            stride=8,
            pixels=bytes((0, 255, 0, 0)) * 2,
        )
        presenter = OutputVideoRepresentativeFramePresenter(document)

        assert presenter.present(media_id, frame)
        assert document.composition_id_for(media_id) == composition_id
        assert document.image_path(media_id) == video_path
        assert document.workspace.canvasFor(composition_id) is target
        assert _wait_for_rendered_color(app, target, QColor("lime"))
    finally:
        document.close()
        destroy_qt_object(document.workspace)
        destroy_qt_object(document)
