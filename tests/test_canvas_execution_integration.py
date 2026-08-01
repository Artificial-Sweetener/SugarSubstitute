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

"""Verify production canvas documents share the host-adapted CuteCanvas runtime."""

from __future__ import annotations

import threading
import time
from functools import partial

from PySide6.QtWidgets import QApplication
from cutecanvas import (
    ExecutionHandle,
    ExecutionLeaseRelease,
    ExecutionRequest,
    ExecutionRequirements,
    ExecutionResource,
)

from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.app.bootstrap.canvas_execution_runtime import (
    CanvasExecutionRuntime,
)
from substitute.presentation.canvas.input.input_document import InputCanvasDocument
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument


def test_input_and_output_documents_share_the_host_canvas_runtime() -> None:
    """Inject one host-owned canvas runtime with separate document scopes."""

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


def test_input_native_work_uses_the_host_execution_runtime() -> None:
    """Keep stable-affinity editor work inside the process execution owner."""

    application = QApplication.instance() or QApplication([])
    host_runtime = ExecutionRuntime()
    input_document = InputCanvasDocument(
        features=("mask",),
        execution_runtime=host_runtime.canvas_execution_runtime,
    )
    try:
        document_runtime = input_document.runtime
        native_scope = document_runtime.native_execution_scope()

        assert native_scope is document_runtime.execution_scope

        handle = native_scope.submit(
            ExecutionRequest[str, object](
                operation="test.host_native_affinity",
                requirements=ExecutionRequirements(
                    resource=ExecutionResource.THREAD_AFFINE_NATIVE,
                    affinity_key="test-host-native",
                    exclusive_key="test-host-native",
                    lease_release=ExecutionLeaseRelease.ADOPTION_FINISHED,
                ),
                work=lambda _context: threading.current_thread().name,
            )
        )

        deadline = time.monotonic() + 1.0
        while handle.outcome is None and time.monotonic() < deadline:
            application.processEvents()

        assert handle.outcome is not None
        assert handle.outcome.result is not None
        assert handle.outcome.result.startswith("substitute-")
        assert not handle.outcome.result.startswith("qpane-affinity-")
    finally:
        input_document.canvas.deleteLater()
        application.processEvents()
        host_runtime.shutdown()


def test_canvas_execution_binding_survives_repeated_hostile_teardown() -> None:
    """Release every ordinary, affinity, and diagnostics thread repeatedly."""

    for iteration in range(16):
        binding = CanvasExecutionRuntime()
        runtime = binding.runtime
        diagnostics = runtime.subscribe_diagnostics(lambda _snapshots: None)
        scope = runtime.open_scope(
            owner_id=f"teardown-{iteration}",
            dispatcher=None,
        )
        handles: list[ExecutionHandle[str, object]] = [
            scope.submit(
                ExecutionRequest(
                    operation=f"ordinary_{iteration}",
                    work=lambda _context: threading.current_thread().name,
                )
            ),
            scope.submit(
                ExecutionRequest(
                    operation=f"affinity_{iteration}",
                    requirements=ExecutionRequirements(
                        resource=ExecutionResource.THREAD_AFFINE_NATIVE,
                        affinity_key=f"teardown-affinity-{iteration}",
                    ),
                    work=lambda _context: threading.current_thread().name,
                )
            ),
        ]
        settled = [threading.Event() for _handle in handles]
        for handle, event in zip(handles, settled, strict=True):
            handle.add_done_callback(partial(_signal_settlement, event=event))
        assert all(event.wait(timeout=1.0) for event in settled)

        diagnostics.close()
        binding.shutdown(wait=True)

        snapshot = binding.scheduler.snapshot()
        assert snapshot.accepted == 0
        assert snapshot.pending == 0
        assert snapshot.running == 0
        assert snapshot.worker_threads == 0
        assert not any(
            thread.name.startswith("substitute-canvas-") and thread.is_alive()
            for thread in threading.enumerate()
        )


def _signal_settlement(_outcome: object, *, event: threading.Event) -> None:
    """Signal one terminal execution outcome."""

    event.set()
