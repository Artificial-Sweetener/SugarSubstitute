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

"""Capture the most recently executed projection content-cache paint path."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptPaintIdentity,
)

from .paint_input import PromptProjectionPaintStyleKey
from .content_media_state import PromptProjectionContentMediaIdentity


@dataclass(frozen=True, slots=True)
class PromptProjectionContentCacheKey:
    """Identify one reusable viewport-local projection content pixmap."""

    paint_identity: PromptPaintIdentity
    style: PromptProjectionPaintStyleKey
    media_identity: PromptProjectionContentMediaIdentity


@dataclass(frozen=True, slots=True)
class PromptProjectionContentCacheSnapshot:
    """Expose immutable content-cache state for diagnostics and contracts."""

    key: PromptProjectionContentCacheKey | None
    has_pixmap: bool
    last_paint_result: str
    last_paint_identity: PromptPaintIdentity | None


class PromptProjectionPaintCacheTelemetry:
    """Own diagnostic state from the last content-cache paint operation."""

    def __init__(self) -> None:
        """Initialize telemetry before any content has been painted."""

        self._result = "unpainted"
        self._identity: PromptPaintIdentity | None = None

    def record(
        self, result: str, *, paint_identity: PromptPaintIdentity | None
    ) -> None:
        """Record the exact frame identity observed by one paint path."""

        self._result = result
        self._identity = paint_identity

    def snapshot(
        self,
        *,
        key: PromptProjectionContentCacheKey | None,
        has_pixmap: bool,
    ) -> PromptProjectionContentCacheSnapshot:
        """Return immutable cache and latest-paint diagnostics."""

        return PromptProjectionContentCacheSnapshot(
            key=key,
            has_pixmap=has_pixmap,
            last_paint_result=self._result,
            last_paint_identity=self._identity,
        )


__all__ = [
    "PromptProjectionContentCacheKey",
    "PromptProjectionContentCacheSnapshot",
    "PromptProjectionPaintCacheTelemetry",
]
