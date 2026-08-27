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

"""Own deterministic execution and document lifetime for Output tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from cutecanvas import ExecutionRuntime

from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


@pytest.fixture
def output_document(
    execution_runtime: ExecutionRuntime,
) -> Iterator[OutputCanvasDocument]:
    """Provide one exactly destroyed Output document without production workers."""

    ensure_qt_application()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    try:
        yield document
    finally:
        document.close()
        destroy_qt_object(document)
