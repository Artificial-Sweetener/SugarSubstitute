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

"""Verify Output-canvas pipeline and progress-strip composition."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from substitute.presentation.shell import main_window_composition


class _PromptActivity:
    """Provide deterministic prompt-interaction callbacks."""

    def is_prompt_interaction_active(self) -> bool:
        """Report no active prompt interaction."""

        return False

    def ms_since_last_prompt_interaction(self) -> int:
        """Report a stable elapsed interaction interval."""

        return 0


class _OutputImagePipeline:
    """Capture output-pipeline constructor dependencies."""

    def __init__(self, **kwargs: object) -> None:
        """Store pipeline construction inputs."""

        self.kwargs = kwargs


class _PreparationDispatcher:
    """Provide the output preparation cleanup endpoint."""

    def shutdown(self) -> None:
        """Represent dispatcher shutdown."""


class _ProgressStripRegistry:
    """Capture the owning shell for progress-strip registration."""

    def __init__(self, parent: object) -> None:
        """Store the registry parent."""

        self.parent = parent


class _ResourceLifecycle:
    """Record named cleanup registrations."""

    def __init__(self) -> None:
        """Initialize no registered resources."""

        self.registrations: list[tuple[str, Callable[[], None]]] = []

    def register(self, name: str, cleanup: Callable[[], None]) -> None:
        """Record one resource cleanup callback."""

        self.registrations.append((name, cleanup))


class _FloatingChromeFactory:
    """Capture the progress-strip registry supplied by composition."""

    def __init__(self) -> None:
        """Initialize no registry assignment."""

        self.registrations: list[object] = []

    def set_progress_strip_registry(self, registry: object) -> None:
        """Record the composed progress-strip registry."""

        self.registrations.append(registry)


class _Shell:
    """Hold Output-canvas composition inputs and outputs."""

    def __init__(self) -> None:
        """Create the minimal Output-canvas shell contract."""

        self.workflow_session_service = object()
        self.canvas_io_service = object()
        self.workspace_canvas_actions = object()
        self.output_canvas_projection_coordinator = object()
        self.canvas_host = object()
        self.generation_job_queue_service = object()
        self.output_floating_chrome_factory = _FloatingChromeFactory()
        self.prompt_interaction_activity_tracker = _PromptActivity()
        self.shell_resource_lifecycle = _ResourceLifecycle()
        self.output_image_pipeline: object | None = None
        self.generation_progress_strip_registry: object | None = None
        self.output_transfer_lifecycle: object | None = None


def test_compose_output_canvas_controllers_assigns_pipeline_and_strip_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose output pipeline, transfer lifecycle, and progress-strip registry."""

    monkeypatch.setattr(
        main_window_composition,
        "OutputImagePipeline",
        _OutputImagePipeline,
    )
    monkeypatch.setattr(
        main_window_composition,
        "GenerationProgressStripRegistry",
        _ProgressStripRegistry,
    )
    transfer_lifecycle = object()
    monkeypatch.setattr(
        main_window_composition,
        "_compose_output_transfer_lifecycle",
        lambda _shell: transfer_lifecycle,
    )
    preparation_dispatcher = _PreparationDispatcher()
    monkeypatch.setattr(
        main_window_composition,
        "_output_image_preparation_dispatcher",
        lambda _shell: preparation_dispatcher,
    )
    shell = _Shell()

    composition = main_window_composition.compose_output_canvas_controllers(shell)

    assert composition.output_image_pipeline is shell.output_image_pipeline
    assert (
        composition.generation_progress_strip_registry
        is shell.generation_progress_strip_registry
    )
    assert composition.output_transfer_lifecycle is shell.output_transfer_lifecycle
    assert shell.output_transfer_lifecycle is transfer_lifecycle
    pipeline = shell.output_image_pipeline
    assert isinstance(pipeline, _OutputImagePipeline)
    assert pipeline.kwargs == {
        "workflow_session_service": shell.workflow_session_service,
        "canvas_io_service": shell.canvas_io_service,
        "output_commit_handler": shell.workspace_canvas_actions,
        "output_canvas_projection_coordinator": (
            shell.output_canvas_projection_coordinator
        ),
        "canvas_host": shell.canvas_host,
        "generation_timing_lookup": shell.generation_job_queue_service,
        "prompt_interaction_active": (
            shell.prompt_interaction_activity_tracker.is_prompt_interaction_active
        ),
        "prompt_interaction_elapsed_ms": (
            shell.prompt_interaction_activity_tracker.ms_since_last_prompt_interaction
        ),
        "preparation_dispatcher": preparation_dispatcher,
        "parent": shell,
    }
    registry = shell.generation_progress_strip_registry
    assert isinstance(registry, _ProgressStripRegistry)
    assert registry.parent is shell
    assert shell.output_floating_chrome_factory.registrations == [registry]
    assert shell.shell_resource_lifecycle.registrations == [
        ("output_image_preparation", preparation_dispatcher.shutdown)
    ]
