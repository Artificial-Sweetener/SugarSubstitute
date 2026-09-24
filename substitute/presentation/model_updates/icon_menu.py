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

"""Present update-specific choices from a model's version icon."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import RoundMenu  # type: ignore[import-untyped]

from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from sugarsubstitute_shared.localization import app_text


def update_icon_menu(
    *, parent: QWidget, updates: ModelUpdatePickerBridge, sha256: str | None
) -> RoundMenu | None:
    """Build only the two actions relevant to the exact visible update icon."""

    proposal = updates.proposal_for_sha(sha256)
    if proposal is None:
        return None

    def dismiss() -> None:
        """Persist dismissal of only the currently offered release."""

        updates.request_dismissal(sha256)

    def disable_page() -> None:
        """Persist the page-level opt-out selected from the icon."""

        updates.request_page_opt_out(sha256)

    return QFluentMenuRenderer(parent=parent).render(
        MenuModel(
            entries=(
                MenuItem(
                    action_id="dismiss-model-update",
                    label=app_text("Dismiss"),
                    callback=dismiss,
                ),
                MenuItem(
                    action_id="disable-model-page-updates",
                    label=app_text(
                        "Don't check for updates for %1",
                        proposal.candidate.model_name,
                    ),
                    callback=disable_page,
                ),
            )
        )
    )


def show_update_icon_menu(
    *,
    parent: QWidget,
    updates: ModelUpdatePickerBridge,
    sha256: str | None,
    global_pos: QPoint,
) -> bool:
    """Open the icon-only menu at the pointer without changing model selection."""

    menu = update_icon_menu(parent=parent, updates=updates, sha256=sha256)
    if menu is None:
        return False
    menu.exec(global_pos)
    return True


__all__ = ["show_update_icon_menu", "update_icon_menu"]
