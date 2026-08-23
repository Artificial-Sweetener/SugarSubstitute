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

"""Characterize authorization and revision safety for Output transfer resolution."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from tests.presentation.canvas.output.transfer.support import (
    build_transfer_resolver,
    transfer_image,
)


def test_resolver_uses_captured_current_authorized_document_content(
    tmp_path: Path,
    output_document: OutputCanvasDocument,
) -> None:
    """A captured composition should resolve to its matching staged PNG artifact."""

    image_id = uuid4()
    assert output_document.admit_image(image_id, transfer_image("red"))
    reference = output_document.content_reference_for(image_id)
    assert reference is not None
    resolver = build_transfer_resolver(output_document, tmp_path, {image_id})

    resolved = resolver.resolve(reference)

    assert resolved is not None
    assert resolved.image_id == image_id
    assert resolved.artifact.mime_type == "image/png"
    assert resolved.artifact.staged is True


def test_resolver_rejects_foreign_or_replaced_document_subjects(
    tmp_path: Path,
    output_document: OutputCanvasDocument,
) -> None:
    """Retired and product-unauthorized content must never materialize a transfer."""

    image_id = uuid4()
    assert output_document.admit_image(image_id, transfer_image("red"))
    reference = output_document.content_reference_for(image_id)
    assert reference is not None
    assert (
        build_transfer_resolver(output_document, tmp_path, set()).resolve(reference)
        is None
    )

    assert output_document.admit_image(image_id, transfer_image("blue"))
    assert (
        build_transfer_resolver(output_document, tmp_path, {image_id}).resolve(
            reference
        )
        is None
    )
