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

"""Verify Output document ownership ends before native shell destruction."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtGui import QImage

from substitute.presentation.shell.output_image_commit_pipeline import (
    PreparedOutputImage,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)


def test_shell_shutdown_releases_output_document_before_widgets(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Retire mounted Output targets while their native host remains alive."""

    output_canvas = harness.shell.canvas_host.canvas_for("Output")
    document = output_canvas.document
    image = QImage(64, 64, QImage.Format.Format_ARGB32)
    image.fill(0xFF00FF00)
    image_id = uuid4()
    assert document.admit_image(image_id, image)
    document.present_single(image_id)
    assert document.image_ids() == (image_id,)

    harness.shell.shell_resource_lifecycle.shutdown_or_raise()

    assert document.image_ids() == ()


def test_shell_shutdown_discards_decoded_output_waiting_for_commit(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep late output delivery from mutating a retired shell or document."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    run = harness.start_run("alpha")
    closed = False

    def close_after_decode(_prepared: PreparedOutputImage) -> None:
        """Close at the boundary between background decode and queued GUI commit."""
        nonlocal closed
        harness.shell.shell_resource_lifecycle.shutdown_or_raise()
        closed = True

    harness.shell.output_image_pipeline._preparation_dispatcher.prepared.connect(
        close_after_decode
    )
    harness.emit_output(run, OutputSpec("alpha:text", "Text", (50, 100, 150)))
    wait_for_qt_condition(lambda: closed, description="shell retirement after decode")
    wait_for_queued_qt_turn()

    assert harness.output_count("alpha") == 0
    assert harness.shell.output_canvas.document.image_ids() == ()
