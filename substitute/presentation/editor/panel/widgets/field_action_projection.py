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

"""Project semantic field-action sources into node-menu contributions."""

from __future__ import annotations

from substitute.presentation.editor.field_actions import (
    FieldActionContribution,
    FieldActionSource,
)


def field_action_contributions(
    sources: tuple[tuple[str, object], ...],
) -> tuple[FieldActionContribution, ...]:
    """Adapt semantic action sources into stable node-menu contributions."""

    return tuple(
        FieldActionContribution(
            contribution_id=f"field.{field_key}",
            availability_factory=source.field_actions_available,
            entries_factory=source.field_action_entries,
        )
        for field_key, source in sources
        if isinstance(source, FieldActionSource)
    )
