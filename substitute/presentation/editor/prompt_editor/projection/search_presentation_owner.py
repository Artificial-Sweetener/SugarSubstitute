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

"""Own prompt search state transitions and render publication."""

from __future__ import annotations

from collections.abc import Callable

from .session import PromptProjectionSession


class PromptSearchPresentationOwner:
    """Publish search match state through the prepared render pipeline."""

    def __init__(
        self,
        *,
        session: PromptProjectionSession,
        publish_changed: Callable[[], None],
        publish_cleared: Callable[[], None],
        request_update: Callable[[], None],
    ) -> None:
        """Bind authoritative search session state to render invalidation."""

        self._session = session
        self._publish_changed = publish_changed
        self._publish_cleared = publish_cleared
        self._request_update = request_update

    def set_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        *,
        active_index: int | None,
    ) -> None:
        """Publish replacement search matches and active match identity."""

        self._session.set_search_matches(matches, active_index=active_index)
        self._publish_changed()
        self._request_update()

    def clear_matches(self) -> None:
        """Clear search matches and invalidate their prepared layer."""

        self._session.clear_search_matches()
        self._publish_cleared()
        self._request_update()


__all__ = ["PromptSearchPresentationOwner"]
