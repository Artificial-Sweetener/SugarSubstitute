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

"""Define dynamic inputs shared by focused projection-building strategies."""

from __future__ import annotations

from typing import Protocol

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)

from .freshness_controller import PromptProjectionFreshnessBlockers
from .session import PromptProjectionSession


class PromptProjectionBuildContext(Protocol):
    """Expose mutable feature state read only when a strategy builds projection."""

    _display_mode: PromptProjectionDisplayMode
    _session: PromptProjectionSession
    _scene_error_keys: frozenset[str]

    def _decoration_accent_ranges(self) -> tuple[tuple[int, int], ...]:
        """Return source ranges receiving semantic decoration accents."""

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return current blockers for local projection construction."""


__all__ = ["PromptProjectionBuildContext"]
