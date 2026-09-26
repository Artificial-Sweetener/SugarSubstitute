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

"""Render the global-override menu from semantic toolbar candidates."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import QWidget
from sugarsubstitute_shared.presentation.localization import set_localized_tooltip

from substitute.application.display_labels import beautify_label
from substitute.application.overrides import OverrideToolbarSnapshot
from substitute.presentation.widgets.menu_model import MenuItem
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer


class OverrideMenuPresenter:
    """Populate one mounted menu without owning selection or workflow state."""

    def rebuild(
        self,
        *,
        menu: Any,
        dropdown_button: Any,
        snapshot: OverrideToolbarSnapshot,
        is_selected: Callable[[str], bool],
    ) -> None:
        """Replace menu entries with the current semantic override candidates."""

        if menu is None:
            return
        menu.clear()
        entries = tuple(
            MenuItem(
                f"global_override.{candidate.override_key}",
                beautify_label(candidate.label),
                checkable=True,
                checked=is_selected(candidate.override_key),
                data={"override_key": candidate.override_key},
            )
            for candidate in snapshot.candidates
        )
        QFluentMenuRenderer(parent=cast(QWidget, menu)).populate_menu(menu, entries)
        if dropdown_button is not None:
            set_localized_tooltip(dropdown_button, "Set Global Override")


__all__ = ["OverrideMenuPresenter"]
