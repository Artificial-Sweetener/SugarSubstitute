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

"""Own source-line chrome configuration publication effects."""

from __future__ import annotations

from collections.abc import Callable

from .source_line_chrome import PromptSourceLineChrome


class PromptSourceLinePresentationOwner:
    """Coordinate source-line configuration with layout and render publication."""

    def __init__(
        self,
        *,
        chrome: PromptSourceLineChrome,
        flush_pending_projection: Callable[[str], None],
        synchronize_layout: Callable[[], None],
        publish_configuration_changed: Callable[[], None],
        request_update: Callable[[], None],
    ) -> None:
        """Bind source-line state to its required publication effects."""

        self._chrome = chrome
        self._flush_pending_projection = flush_pending_projection
        self._synchronize_layout = synchronize_layout
        self._publish_configuration_changed = publish_configuration_changed
        self._request_update = request_update

    def set_enabled(self, enabled: bool) -> None:
        """Publish changed source-line visibility."""

        if not self._chrome.set_enabled(enabled):
            return
        self._publish_configuration_changed()
        self._request_update()

    def set_content_left_inset(self, inset: float) -> None:
        """Publish changed source-line inset and its new layout geometry."""

        inset = max(0.0, inset)
        if abs(self._chrome.content_left_inset - inset) < 0.01:
            return
        self._flush_pending_projection("set_source_line_content_left_inset")
        self._chrome.set_content_left_inset(inset)
        self._synchronize_layout()
        self._request_update()


__all__ = ["PromptSourceLinePresentationOwner"]
