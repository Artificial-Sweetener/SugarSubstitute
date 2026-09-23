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

"""Test focused prompt fill-band publication ownership."""

from __future__ import annotations

from typing import Never

from PySide6.QtGui import QColor

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.projection.fill_band_owner import (
    PromptProjectionFillBandOwner,
)
from substitute.presentation.editor.prompt_editor.projection.freshness_controller import (
    PromptProjectionFreshnessController,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_geometry import (
    PromptProjectionReorderGeometry,
)


def _unexpected_input() -> Never:
    """Fail if raw-mode publication samples projection-only inputs."""

    raise AssertionError("raw fill-band publication sampled projection state")


def test_raw_mode_returns_no_bands_without_sampling_projection_state() -> None:
    """Raw text mode should bypass every projected fill-band dependency."""

    owner = PromptProjectionFillBandOwner(
        freshness=PromptProjectionFreshnessController(
            apply_update=lambda _update: None,
            parent=None,
        ),
        display_mode=lambda: PromptProjectionDisplayMode.RAW,
        current_source_identity=_unexpected_input,
        committed_source_text=_unexpected_input,
        live_source_text=_unexpected_input,
        viewport_rect=_unexpected_input,
        scroll_offset=_unexpected_input,
        content_width=_unexpected_input,
        content_left_inset=_unexpected_input,
        reorder_geometry=PromptProjectionReorderGeometry(),
        geometry_state=_unexpected_input,
    )

    assert owner.visible_rects() == ()
    assert isinstance(owner.color(), QColor)
