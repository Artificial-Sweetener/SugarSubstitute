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

"""Verify production canvas documents share the host-adapted QPane runtime."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument


def test_input_and_output_documents_share_the_host_canvas_runtime() -> None:
    """Inject one host-owned QPane runtime while retaining separate document scopes."""

    application = QApplication.instance() or QApplication([])
    host_runtime = ExecutionRuntime()
    input_document = InputCanvasDocument(
        features=("mask",),
        execution_runtime=host_runtime.canvas_execution_runtime,
    )
    output_document = OutputCanvasDocument(
        execution_runtime=host_runtime.canvas_execution_runtime,
    )
    try:
        assert (
            input_document.runtime.execution_runtime
            is host_runtime.canvas_execution_runtime
        )
        assert (
            output_document.runtime.execution_runtime
            is host_runtime.canvas_execution_runtime
        )
        assert (
            input_document.runtime.execution_scope
            is not output_document.runtime.execution_scope
        )
    finally:
        input_document.canvas.deleteLater()
        output_document.close()
        application.processEvents()
        host_runtime.shutdown()
