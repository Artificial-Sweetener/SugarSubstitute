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

"""Render interactive Settings search results."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Callable

from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel  # type: ignore[import-untyped]

from substitute.presentation.settings.settings_card import (
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.settings.settings_search import SettingsSearchResult
from substitute.presentation.settings.settings_style import SETTINGS_CARD_GROUP_SPACING

SettingsSearchActivationHandler = Callable[[SettingsSearchResult], None]


class SettingsSearchPage(QWidget):
    """Show Settings search results as metadata-backed navigation rows."""

    def __init__(
        self,
        results: tuple[SettingsSearchResult, ...],
        *,
        on_result_activated: SettingsSearchActivationHandler | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create a search page for one debounced query result."""

        super().__init__(parent)
        self._results = results
        self._on_result_activated = on_result_activated
        self._build_layout()

    def _build_layout(self) -> None:
        """Render matching controls or a no-results state."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_CARD_GROUP_SPACING)
        if not self._results:
            layout.addWidget(
                SettingsCard(
                    title=app_text("No settings found"),
                    description=app_text("Try a different search term."),
                    reserve_visual_space=False,
                    parent=self,
                )
            )
            layout.addStretch(1)
            return
        for result in self._results:
            context = BodyLabel(result.breadcrumb, self)
            context.setObjectName("SettingsSearchResultBreadcrumb")
            layout.addWidget(context)
            card = InteractiveSettingsCard(
                title=result.control.title,
                description=result.control.description,
                reserve_visual_space=False,
                show_chevron=True,
                parent=self,
            )
            card.setObjectName("SettingsSearchResultCard")
            card.activated.connect(
                lambda checked=False, item=result: self._activate_result(item)
            )
            layout.addWidget(card)
        layout.addStretch(1)

    def _activate_result(self, result: SettingsSearchResult) -> None:
        """Notify the workspace that one metadata search result was opened."""

        if self._on_result_activated is not None:
            self._on_result_activated(result)


__all__ = ["SettingsSearchActivationHandler", "SettingsSearchPage"]
