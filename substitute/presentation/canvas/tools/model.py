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

"""Define inert runtime canvas-tool contributions and projected presentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sugarsubstitute_shared.localization import ApplicationText


class CanvasToolKind(str, Enum):
    """Distinguish persistent interaction modes from one-shot actions."""

    MODE = "mode"
    ACTION = "action"


@dataclass(frozen=True, slots=True)
class CanvasToolContribution:
    """Describe one runtime-addable canvas tool without owning execution."""

    tool_id: str
    label: ApplicationText
    icon: object
    kind: CanvasToolKind
    section: str
    order: int
    required_context_tags: frozenset[str] = field(default_factory=frozenset)
    required_capabilities: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        """Reject identities and placement metadata that cannot remain stable."""

        if not self.tool_id or self.tool_id != self.tool_id.strip():
            raise ValueError("canvas tool tool_id must be a non-blank stable ID")
        if not self.section or self.section != self.section.strip():
            raise ValueError("canvas tool section must be a non-blank stable ID")
        if self.icon is None:
            raise ValueError("canvas tool icon must not be None")
        if any(not tag or tag != tag.strip() for tag in self.required_context_tags):
            raise ValueError("canvas tool context tags must be non-blank stable IDs")
        if any(
            not capability or capability != capability.strip()
            for capability in self.required_capabilities
        ):
            raise ValueError("canvas tool capabilities must be non-blank stable IDs")


@dataclass(frozen=True, slots=True)
class CanvasToolContext:
    """Describe the active surface and its currently authorized capabilities."""

    tags: frozenset[str] = field(default_factory=frozenset)
    capabilities: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class CanvasToolPresentation:
    """Project one contribution into current visibility, availability, and state."""

    contribution: CanvasToolContribution
    enabled: bool
    active: bool

    @property
    def tool_id(self) -> str:
        """Return the stable contribution identity."""

        return self.contribution.tool_id

    @property
    def label(self) -> ApplicationText:
        """Return the contribution's user-facing label."""

        return self.contribution.label

    @property
    def icon(self) -> object:
        """Return the contribution's resolved presentation icon."""

        return self.contribution.icon

    @property
    def kind(self) -> CanvasToolKind:
        """Return whether the contribution is a persistent mode or action."""

        return self.contribution.kind

    @property
    def section(self) -> str:
        """Return the contribution's visual grouping identity."""

        return self.contribution.section


__all__ = [
    "CanvasToolContext",
    "CanvasToolContribution",
    "CanvasToolKind",
    "CanvasToolPresentation",
]
