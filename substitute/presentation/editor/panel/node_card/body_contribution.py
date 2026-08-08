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

"""Define the extension boundary for focused node-card body features."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.presentation.editor.panel.widgets.field_row import BuiltFieldRow


@dataclass(frozen=True, slots=True)
class NodeCardBodyContributionContext:
    """Provide graph and node identity without exposing NodeCardBuilder internals."""

    section_key: str
    node_name: str
    node_type: str
    inputs: Mapping[str, object]
    graph: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class NodeCardBodyContribution:
    """Describe a normal field row that receives focused feature behavior."""

    field_keys: tuple[str, ...]
    row_decorator: NodeCardBodyRowDecorator

    @property
    def claimed_field_keys(self) -> frozenset[str]:
        """Return the fields owned by this contribution for exact matching."""

        return frozenset(self.field_keys)


class NodeCardBodyRowDecorator(Protocol):
    """Apply focused behavior after the normal field row has been built."""

    def decorate(self, built_row: BuiltFieldRow) -> None:
        """Decorate the row without replacing its field widgets."""


class NodeCardBodyContributor(Protocol):
    """Build one optional focused row for a node card."""

    def build(
        self,
        context: NodeCardBodyContributionContext,
    ) -> NodeCardBodyContribution | None:
        """Return a contribution when this collaborator owns the node role."""


__all__ = [
    "NodeCardBodyContribution",
    "NodeCardBodyContributionContext",
    "NodeCardBodyContributor",
    "NodeCardBodyRowDecorator",
]
