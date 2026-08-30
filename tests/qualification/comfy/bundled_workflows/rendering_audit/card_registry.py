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

"""Read direct-workflow card and field registries from production panels."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtWidgets import QWidget

from substitute.application.workflows.editor_projection_service import (
    DIRECT_WORKFLOW_SECTION_KEY,
)


def card_map(raw_cards: Mapping[object, object]) -> dict[str, QWidget]:
    """Return direct-section registered cards indexed by production identity."""

    cards: dict[str, QWidget] = {}
    for key, card in raw_cards.items():
        if (
            isinstance(key, tuple)
            and len(key) == 2
            and key[0] == DIRECT_WORKFLOW_SECTION_KEY
            and isinstance(key[1], str)
            and isinstance(card, QWidget)
        ):
            cards[key[1]] = card
    return cards


def field_map(
    raw_fields: Mapping[object, object],
) -> dict[tuple[str, str], QWidget]:
    """Return direct-section registered fields indexed by production identity."""

    fields: dict[tuple[str, str], QWidget] = {}
    for key, widget in raw_fields.items():
        if (
            isinstance(key, tuple)
            and len(key) == 3
            and key[0] == DIRECT_WORKFLOW_SECTION_KEY
            and isinstance(key[1], str)
            and isinstance(key[2], str)
            and isinstance(widget, QWidget)
        ):
            fields[(key[1], key[2])] = widget
    return fields
