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

"""Verify bounded prompt diagnostic geometry and raster cache policy."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.diagnostic_fragment_cache import (
    PromptDiagnosticFragmentCache,
)
from substitute.presentation.editor.prompt_editor.projection.diagnostic_render_layer import (
    PromptDiagnosticFragmentKey,
    PromptDiagnosticViewportIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.diagnostic_wave_tiles import (
    PromptDiagnosticWaveTileCache,
)


def _fragment_key(index: int) -> PromptDiagnosticFragmentKey:
    """Build one distinct cache key without irrelevant revision construction."""

    return PromptDiagnosticFragmentKey(
        diagnostic_id=f"diagnostic-{index}",
        source_start=index,
        source_end=index + 1,
        viewport=PromptDiagnosticViewportIdentity(
            layout_identity=cast(PromptLayoutIdentity, object()),
            viewport_x=0,
            viewport_y=0,
            viewport_width=100,
            viewport_height=100,
            scroll_offset=0,
        ),
    )


def test_diagnostic_fragment_cache_evicts_only_least_recent_entry() -> None:
    """Bounded fragment overflow should preserve recently used geometry."""

    cache = PromptDiagnosticFragmentCache(capacity=2)
    first = _fragment_key(1)
    second = _fragment_key(2)
    third = _fragment_key(3)
    cache.put(first, (QRectF(1.0, 0.0, 1.0, 1.0),))
    cache.put(second, (QRectF(2.0, 0.0, 1.0, 1.0),))

    assert cache.get(first) is not None
    cache.put(third, (QRectF(3.0, 0.0, 1.0, 1.0),))

    assert cache.contains(first)
    assert not cache.contains(second)
    assert cache.contains(third)


def test_diagnostic_wave_tile_cache_is_bounded_and_reuses_exact_style(
    qt_application_owner: QApplication,
) -> None:
    """Wave raster styles should use bounded exact-key reuse."""

    _ = qt_application_owner
    cache = PromptDiagnosticWaveTileCache(capacity=2)
    first = cache.tile(
        color=QColor("red"),
        radius=2.0,
        pen_width=1.2,
        device_pixel_ratio=1.0,
    )
    repeated = cache.tile(
        color=QColor("red"),
        radius=2.0,
        pen_width=1.2,
        device_pixel_ratio=1.0,
    )
    cache.tile(
        color=QColor("green"),
        radius=2.0,
        pen_width=1.2,
        device_pixel_ratio=1.0,
    )
    cache.tile(
        color=QColor("blue"),
        radius=2.0,
        pen_width=1.2,
        device_pixel_ratio=1.0,
    )

    assert repeated.cacheKey() == first.cacheKey()
    assert cache.entry_count == 2
