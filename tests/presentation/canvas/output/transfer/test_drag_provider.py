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

"""Characterize captured-subject execution for native Output drag materialization."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from cutecanvas import DragSubject

from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_transfer_drag_provider import (
    OutputTransferDragProvider,
)
from tests.presentation.canvas.output.transfer.support import (
    ImmediateTaskSubmitter,
    build_transfer_resolver,
    transfer_image,
)


def test_drag_provider_materializes_the_captured_document_subject(
    tmp_path: Path,
    output_document: OutputCanvasDocument,
) -> None:
    """Native drag payload must represent the pressed content, not active state."""

    image_id = uuid4()
    assert output_document.admit_image(image_id, transfer_image())
    reference = output_document.content_reference_for(image_id)
    assert reference is not None
    provider = OutputTransferDragProvider(
        resolver=build_transfer_resolver(output_document, tmp_path, {image_id}),
        submitter=ImmediateTaskSubmitter(),
    )
    published: list[tuple[object | None, BaseException | None]] = []

    cancellation = provider.materialize(
        DragSubject(reference),
        lambda payload, error: published.append((payload, error)),
    )

    assert cancellation is not None
    assert len(published) == 1
    payload, error = published[0]
    assert error is None
    assert payload is not None
    assert hasattr(payload, "items")
    assert hasattr(payload, "urls")
    assert payload.items[0].mime_type == "image/png"
    assert payload.urls[0].toLocalFile().endswith(".png")


def test_drag_provider_rejects_retired_captured_subject(
    tmp_path: Path,
    output_document: OutputCanvasDocument,
) -> None:
    """Replacing content before materialization must not start a stale native drag."""

    image_id = uuid4()
    assert output_document.admit_image(image_id, transfer_image())
    reference = output_document.content_reference_for(image_id)
    assert reference is not None
    assert output_document.admit_image(image_id, transfer_image("blue"))
    provider = OutputTransferDragProvider(
        resolver=build_transfer_resolver(output_document, tmp_path, {image_id}),
        submitter=ImmediateTaskSubmitter(),
    )
    published: list[tuple[object | None, BaseException | None]] = []

    provider.materialize(
        DragSubject(reference),
        lambda payload, error: published.append((payload, error)),
    )

    assert len(published) == 1
    payload, error = published[0]
    assert payload is None
    assert isinstance(error, RuntimeError)
    assert str(error) == "Output image is no longer available."
