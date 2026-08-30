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

"""Own deterministic Input document lifetime for presentation tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from cutecanvas import ExecutionRuntime

from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from tests.support.cutecanvas.input_document import (
    InputDocumentFactory,
    destroy_input_document,
)


@pytest.fixture
def input_document_factory(
    execution_runtime: ExecutionRuntime,
) -> Iterator[InputDocumentFactory]:
    """Create Input documents on the test runtime and destroy every owned view."""

    documents: list[InputCanvasDocument] = []

    def create_document() -> InputCanvasDocument:
        """Create one mask-capable Input document owned by this test."""

        document = InputCanvasDocument(
            features=("mask",),
            execution_runtime=execution_runtime,
        )
        documents.append(document)
        return document

    try:
        yield create_document
    finally:
        for document in reversed(documents):
            destroy_input_document(document)
