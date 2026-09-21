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

"""Own regional chrome interaction state and paint publication."""

from __future__ import annotations

from collections.abc import Callable

from .region_chrome import PromptRegionChrome
from .region_chrome_state import PromptRegionChromeEditTarget


class PromptRegionChromePresentationOwner:
    """Publish changed hover and inline-edit state for regional prompt chrome."""

    def __init__(
        self,
        *,
        publish_render_frame: Callable[[], None],
        request_update: Callable[[], None],
        chrome: PromptRegionChrome | None = None,
    ) -> None:
        """Create regional chrome and bind its mounted publication effects."""

        self._chrome = chrome or PromptRegionChrome()
        self._publish_render_frame = publish_render_frame
        self._request_update = request_update

    @property
    def chrome(self) -> PromptRegionChrome:
        """Return the geometry owner consumed by layout and render publication."""

        return self._chrome

    def set_hovered_region(self, region_index: int | None) -> None:
        """Publish transient regional hover without changing prompt selection."""

        if self._chrome.set_hovered_region(region_index):
            self._publish_changed_state()

    def edit_target(self, region_index: int) -> PromptRegionChromeEditTarget | None:
        """Return prepared document-local geometry for one separator editor."""

        return self._chrome.edit_target(region_index)

    def set_editing_region(self, region_index: int | None) -> None:
        """Publish label suppression while one separator editor is active."""

        if self._chrome.set_editing_region(region_index):
            self._publish_changed_state()

    def set_editing_region_draft(self, region_index: int, text: str) -> None:
        """Publish live separator geometry without mutating prompt source text."""

        if self._chrome.set_editing_region_draft(region_index, text):
            self._publish_changed_state()

    def _publish_changed_state(self) -> None:
        """Publish a changed regional layer before requesting its repaint."""

        self._publish_render_frame()
        self._request_update()


__all__ = ["PromptRegionChromePresentationOwner"]
