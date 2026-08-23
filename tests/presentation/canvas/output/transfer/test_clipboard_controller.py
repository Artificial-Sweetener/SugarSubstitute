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

"""Characterize captured-subject clipboard publication for Output transfers."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_transfer_clipboard_controller import (
    OutputTransferClipboardController,
)
from tests.presentation.canvas.output.transfer.support import (
    ImmediateTaskSubmitter,
    build_transfer_resolver,
    transfer_image,
)


def test_clipboard_uses_the_captured_document_subject_without_route_activation(
    tmp_path: Path,
    output_document: OutputCanvasDocument,
) -> None:
    """Copy should publish the captured tile's selected MIME data without UI selection."""

    image_id = uuid4()
    published: list[object] = []
    failures: list[str] = []
    assert output_document.admit_image(image_id, transfer_image())
    reference = output_document.content_reference_for(image_id)
    assert reference is not None
    active_composition_id = output_document.session.active_composition_id
    controller = OutputTransferClipboardController(
        resolver=build_transfer_resolver(output_document, tmp_path, {image_id}),
        submitter=ImmediateTaskSubmitter(),
        publish_mime_data=published.append,
        report_failure=failures.append,
    )

    controller.copy(reference)

    assert failures == []
    assert len(published) == 1
    mime_data = published[0]
    assert hasattr(mime_data, "data")
    assert bytes(mime_data.data("image/png").data()).startswith(b"\x89PNG")
    assert output_document.session.active_composition_id == active_composition_id


def test_clipboard_rejects_a_replaced_captured_subject(
    tmp_path: Path,
    output_document: OutputCanvasDocument,
) -> None:
    """A stale context-menu subject must not publish a later image to clipboard."""

    image_id = uuid4()
    published: list[object] = []
    failures: list[str] = []
    assert output_document.admit_image(image_id, transfer_image())
    reference = output_document.content_reference_for(image_id)
    assert reference is not None
    assert output_document.admit_image(image_id, transfer_image("blue"))
    controller = OutputTransferClipboardController(
        resolver=build_transfer_resolver(output_document, tmp_path, {image_id}),
        submitter=ImmediateTaskSubmitter(),
        publish_mime_data=published.append,
        report_failure=failures.append,
    )

    controller.copy(reference)

    assert published == []
    assert failures == ["Output image is no longer available."]
