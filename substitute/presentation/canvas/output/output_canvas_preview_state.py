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

"""Provide the Output canvas preview-registry host adapter."""

from __future__ import annotations

from typing import Any

from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)


def output_preview_registry(host: object) -> OutputPreviewRegistry:
    """Return the application-owned preview registry for an Output host."""

    registry = getattr(host, "_preview_registry", None)
    if isinstance(registry, OutputPreviewRegistry):
        return registry
    if not _is_real_output_canvas_host(host):
        registry = OutputPreviewRegistry()
        setattr(host, "_preview_registry", registry)
        return registry
    raise RuntimeError("Output preview registry must be installed by the shell.")


def _is_real_output_canvas_host(host: object) -> bool:
    """Return whether host is the concrete widget without importing it."""

    host_type: Any = type(host)
    return (
        getattr(host_type, "__name__", "") == "OutputCanvas"
        and getattr(host_type, "__module__", "")
        == "substitute.presentation.canvas.output.output_canvas_view"
    )


__all__ = [
    "output_preview_registry",
]
