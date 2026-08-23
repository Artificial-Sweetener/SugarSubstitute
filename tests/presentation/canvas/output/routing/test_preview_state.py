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

from substitute.application.workflows.output_preview_lifecycle_service import (
    OutputCanvasRevisionCache,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    install_output_preview_registry,
    output_preview_registry,
    output_revision_cache,
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


def test_output_revision_cache_reuses_existing_cache() -> None:
    """Revision-cache adapter should preserve an installed cache."""

    cache = OutputCanvasRevisionCache(
        registry=OutputPreviewRegistry(),
        session=None,
    )
    host = SimpleNamespace(_revision_cache=cache)

    assert output_revision_cache(host) is cache


def test_output_revision_cache_creates_cache_from_registry() -> None:
    """Revision-cache fallback should bind to the host preview registry."""

    registry = OutputPreviewRegistry()
    host = SimpleNamespace(_preview_registry=registry, _output_session=None)

    cache = output_revision_cache(host)

    assert cache.registry is registry
    assert cache.session is None
    assert host._revision_cache is cache


def test_install_output_preview_registry_resets_revision_cache() -> None:
    """Preview registry installation should bind a fresh revision cache."""

    session = object()
    registry = OutputPreviewRegistry()
    old_cache = OutputCanvasRevisionCache(
        registry=OutputPreviewRegistry(),
        session=None,
    )
    host = SimpleNamespace(_output_session=session, _revision_cache=old_cache)

    install_output_preview_registry(host, registry)

    assert host._preview_registry is registry
    assert isinstance(host._revision_cache, OutputCanvasRevisionCache)
    assert host._revision_cache.registry is registry
    assert host._revision_cache.session is session
