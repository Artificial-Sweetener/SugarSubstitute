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

"""Publish the focused query owners bound to one immutable layout input."""

from __future__ import annotations

from dataclasses import dataclass, field

from .caret_navigation import PromptCaretNavigation
from .hit_test import PromptHitTester
from .selection import PromptSelectionGeometry
from .source_line_queries import PromptSourceLineQueries
from .state import PromptProjectionGeometryInput
from .token_geometry import PromptTokenGeometry
from .viewport import PromptViewportGeometry


@dataclass(frozen=True, slots=True)
class PromptProjectionGeometry:
    """Publish focused geometry owners that share one immutable input."""

    input: PromptProjectionGeometryInput
    caret: PromptCaretNavigation = field(init=False)
    hit_testing: PromptHitTester = field(init=False)
    selection: PromptSelectionGeometry = field(init=False)
    source_lines: PromptSourceLineQueries = field(init=False)
    tokens: PromptTokenGeometry = field(init=False)
    viewport: PromptViewportGeometry = field(init=False)

    def __post_init__(self) -> None:
        """Bind each concern owner exactly once to the published input."""

        caret = PromptCaretNavigation(self.input)
        tokens = PromptTokenGeometry(self.input)
        object.__setattr__(self, "caret", caret)
        object.__setattr__(self, "hit_testing", PromptHitTester(self.input, caret))
        object.__setattr__(
            self,
            "selection",
            PromptSelectionGeometry(self.input, tokens),
        )
        object.__setattr__(self, "source_lines", PromptSourceLineQueries(self.input))
        object.__setattr__(self, "tokens", tokens)
        object.__setattr__(self, "viewport", PromptViewportGeometry(self.input))


__all__ = ["PromptProjectionGeometry"]
