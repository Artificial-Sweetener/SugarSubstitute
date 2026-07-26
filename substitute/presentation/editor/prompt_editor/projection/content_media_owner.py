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

"""Own relevant prompt-content media revision publication."""

from __future__ import annotations

from .content_media_state import PromptProjectionContentMediaIdentity


class PromptProjectionContentMediaOwner:
    """Advance content identity only for media that can change current paint."""

    def __init__(self) -> None:
        """Create the initial presentation-only media revision."""

        self._identity = PromptProjectionContentMediaIdentity(revision=0)

    @property
    def identity(self) -> PromptProjectionContentMediaIdentity:
        """Return the current immutable media identity."""

        return self._identity

    def publish_thumbnail(self, storage_key: str) -> bool:
        """Advance after a ready thumbnail matches current prompt content."""

        if not storage_key:
            return False
        self._advance()
        return True

    def publish_cache_reset(self, reason: str) -> bool:
        """Advance after the thumbnail owner clears all prepared media."""

        if not reason:
            return False
        self._advance()
        return True

    def _advance(self) -> None:
        """Publish the next monotonic presentation revision."""

        self._identity = PromptProjectionContentMediaIdentity(
            revision=self._identity.revision + 1
        )


__all__ = ["PromptProjectionContentMediaOwner"]
