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

"""Build cube-picker staging test state."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QApplication, QFrame

from substitute.application.cubes import CubeStackDraftEntry
from substitute.presentation.cube_picker.cube_staging_stack import CubeDraftStack


def ensure_application() -> QApplication:
    """Return the process QApplication, creating it when necessary."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def entry(
    staged_id: str,
    *,
    display_name: str = "Text to Image",
) -> CubeStackDraftEntry:
    """Return one new draft entry for stack tests."""
    return CubeStackDraftEntry(
        draft_id=staged_id,
        source="new",
        cube_id="Example/Base-Cubes/text-to-image.cube",
        display_name=display_name,
        secondary_text="v1.0.0 - base-cubes",
        icon=None,
    )


def existing_entry(staged_id: str, *, alias: str) -> CubeStackDraftEntry:
    """Return one existing draft entry for stack tests."""
    return CubeStackDraftEntry(
        draft_id=staged_id,
        source="existing",
        cube_id="Example/Base-Cubes/text-to-image.cube",
        display_name=alias,
        secondary_text="v1.0.0 - base-cubes",
        icon=None,
        existing_alias=alias,
    )


def card_accessible_names(stack: CubeDraftStack) -> list[str]:
    """Return accessible names for rendered staging cards."""
    return [
        card.accessibleName() for card in stack.findChildren(QFrame, "cubeStagingCard")
    ]
