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

"""Test regional chrome interaction publication ownership."""

from __future__ import annotations

from typing import cast

from substitute.presentation.editor.prompt_editor.projection.region_chrome import (
    PromptRegionChrome,
)
from substitute.presentation.editor.prompt_editor.projection.region_chrome_presentation import (
    PromptRegionChromePresentationOwner,
)


class _RegionChromeRecorder:
    """Return configured regional state transitions for publication tests."""

    def __init__(self) -> None:
        """Create one recorder whose first transition changes state."""

        self.hover_results = [True, False]
        self.editing_results = [True]
        self.draft_results = [False]

    def set_hovered_region(self, region_index: int | None) -> bool:
        """Return the next configured hover result."""

        _ = region_index
        return self.hover_results.pop(0)

    def set_editing_region(self, region_index: int | None) -> bool:
        """Return the next configured editing result."""

        _ = region_index
        return self.editing_results.pop(0)

    def set_editing_region_draft(self, region_index: int, text: str) -> bool:
        """Return the next configured draft result."""

        _ = region_index, text
        return self.draft_results.pop(0)

    def edit_target(self, region_index: int) -> None:
        """Return no prepared target from the focused recorder."""

        _ = region_index
        return None


def test_region_presentation_publishes_only_changed_chrome_state() -> None:
    """Changed regional state should publish before exactly one repaint request."""

    chrome = _RegionChromeRecorder()
    effects: list[str] = []
    owner = PromptRegionChromePresentationOwner(
        chrome=cast(PromptRegionChrome, chrome),
        publish_render_frame=lambda: effects.append("publish"),
        request_update=lambda: effects.append("update"),
    )

    owner.set_hovered_region(1)
    owner.set_hovered_region(1)
    owner.set_editing_region(1)
    owner.set_editing_region_draft(1, "draft")

    assert effects == ["publish", "update", "publish", "update"]
