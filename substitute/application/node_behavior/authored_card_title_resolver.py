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

"""Resolve the authored identity that owns an editor node-card title."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.display_labels import beautify_label


@dataclass(frozen=True, slots=True)
class AuthoredCardTitleRequest:
    """Describe the document-specific title authority for one node card."""

    node_name: str
    source_node_title: str | None
    source_node_title_owns_card_label: bool
    is_subgraph_wrapper: bool


class AuthoredCardTitleResolver:
    """Keep SugarCube identities separate from Comfy presentation metadata."""

    @staticmethod
    def resolve(request: AuthoredCardTitleRequest) -> str | None:
        """Return authored card text, or ``None`` when Comfy owns the fallback."""

        if request.source_node_title_owns_card_label or request.is_subgraph_wrapper:
            return _nonempty_text(request.source_node_title)
        return _nonempty_text(beautify_label(request.node_name))


def _nonempty_text(value: str | None) -> str | None:
    """Reject blank text while preserving authored content byte-for-byte."""

    if value is None or not value.strip():
        return None
    return value


__all__ = ["AuthoredCardTitleRequest", "AuthoredCardTitleResolver"]
