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

"""Verify Output canvas preview-state host adapters."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    output_preview_registry,
)


def test_output_preview_registry_returns_installed_registry() -> None:
    """Preview registry adapter should use an explicitly installed registry."""

    registry = OutputPreviewRegistry()
    host = SimpleNamespace(_preview_registry=registry)

    assert output_preview_registry(host) is registry


def test_output_preview_registry_creates_registry_for_lightweight_hosts() -> None:
    """Legacy lightweight hosts should get a local registry fallback."""

    host = SimpleNamespace()

    registry = output_preview_registry(host)

    assert isinstance(registry, OutputPreviewRegistry)
    assert host._preview_registry is registry


def test_output_preview_registry_requires_registry_for_concrete_widget() -> None:
    """Concrete OutputCanvas hosts should fail closed without shell injection."""

    OutputCanvasHost = type(
        "OutputCanvas",
        (),
        {"__module__": "substitute.presentation.canvas.output.output_canvas_view"},
    )

    with pytest.raises(RuntimeError, match="preview registry"):
        output_preview_registry(OutputCanvasHost())
