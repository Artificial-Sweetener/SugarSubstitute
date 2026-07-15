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

"""Compose Input and Output canvases into the generic canvas host."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID

from PySide6.QtWidgets import QWidget

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.host import (
    CanvasHostPage,
    CanvasTabManager,
)
from substitute.presentation.canvas.input.input_canvas_view import InputCanvas
from substitute.presentation.canvas.output.output_floating_chrome import (
    OutputFloatingChromeFactory,
)
from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.shell.generation_progress_strip_registry import (
    GenerationProgressStripRegistry,
)
from substitute.shared.startup_trace import trace_span
from substitute.presentation.shell.generation_titlebar_control_registry import (
    GenerationTitleBarControlRegistry,
)


def create_output_floating_chrome_factory(
    *,
    generation_titlebar_control_registry: (
        GenerationTitleBarControlRegistry | None
    ) = None,
    generation_progress_strip_registry: (GenerationProgressStripRegistry | None) = None,
) -> OutputFloatingChromeFactory:
    """Create the Output-owned chrome factory used by floating Output canvases."""

    return OutputFloatingChromeFactory(
        titlebar_control_registry=generation_titlebar_control_registry,
        progress_strip_registry=generation_progress_strip_registry,
    )


def create_canvas_tabs(
    *,
    output_preview_registry: OutputPreviewRegistry,
    open_single_external_editor: (
        Callable[[object, OutputImageMeta], bool] | None
    ) = None,
    open_all_external_editor: (
        Callable[[list[tuple[object, OutputImageMeta]]], bool] | None
    ) = None,
    reveal_output_asset: Callable[[OutputImageMeta], bool] | None = None,
    final_output_payload_lookup: Callable[[UUID], object | None] | None = None,
    final_output_metadata_lookup: Callable[[UUID], OutputImageMeta | None]
    | None = None,
    generation_titlebar_control_registry: (
        GenerationTitleBarControlRegistry | None
    ) = None,
    generation_progress_strip_registry: (GenerationProgressStripRegistry | None) = None,
    output_floating_chrome_factory: OutputFloatingChromeFactory | None = None,
    route_session_boundary: CanvasRouteSessionBoundaryPort | None = None,
) -> CanvasTabManager:
    """Build the app canvas host from explicit Input and Output pages."""

    output_chrome_factory = output_floating_chrome_factory
    if output_chrome_factory is None:
        output_chrome_factory = create_output_floating_chrome_factory(
            generation_titlebar_control_registry=(generation_titlebar_control_registry),
            generation_progress_strip_registry=generation_progress_strip_registry,
        )
    else:
        if generation_titlebar_control_registry is not None:
            output_chrome_factory.set_titlebar_control_registry(
                generation_titlebar_control_registry
            )
        if generation_progress_strip_registry is not None:
            output_chrome_factory.set_progress_strip_registry(
                generation_progress_strip_registry
            )

    with trace_span("canvas_tabs.create.input_canvas"):
        input_canvas = cast(
            QWidget,
            InputCanvas(route_session_boundary=route_session_boundary),
        )
    with trace_span("canvas_tabs.create.output_canvas"):
        output_canvas = cast(
            QWidget,
            OutputCanvas(
                preview_registry=output_preview_registry,
                open_single_external_editor=open_single_external_editor,
                open_all_external_editor=open_all_external_editor,
                reveal_output_asset=reveal_output_asset,
                final_output_payload_lookup=final_output_payload_lookup,
                final_output_metadata_lookup=final_output_metadata_lookup,
                route_session_boundary=route_session_boundary,
            ),
        )
    with trace_span("canvas_tabs.create.manager"):
        manager = CanvasTabManager(
            pages=(
                CanvasHostPage(
                    label="Input",
                    widget=input_canvas,
                    fallback_label="Output",
                ),
                CanvasHostPage(
                    label="Output",
                    widget=output_canvas,
                    floating_chrome_factory=output_chrome_factory,
                ),
            ),
        )
    return manager


__all__ = ["create_canvas_tabs", "create_output_floating_chrome_factory"]
