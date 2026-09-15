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

"""Host shared report content in an existing application's Fluent modal mask."""

from __future__ import annotations
from collections.abc import Callable
from sugarsubstitute_shared.presentation.error_report_presentation import (
    ErrorReportPresentation,
)
from sugarsubstitute_shared.presentation.error_report_view import SharedErrorReportView
from sugarsubstitute_shared.presentation.full_window_modal import FullWindowModalBase


class SharedErrorReportDialog(FullWindowModalBase):
    """Cover an existing app frame while the report owns modal interaction."""

    def __init__(
        self,
        *,
        presentation: ErrorReportPresentation,
        open_console: Callable[[], None] | None = None,
        restart: Callable[[], None] | None = None,
        parent: object | None = None,
    ) -> None:
        """Mount the report view within the outer frame's existing modal contract."""

        super().__init__(parent)
        del open_console
        self.setClosableOnMaskClicked(presentation.dismiss_on_mask)
        self.buttonGroup.hide()
        self.yesButton.hide()
        self.cancelButton.hide()
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.setSpacing(0)
        self.content = SharedErrorReportView(
            presentation=presentation,
            maximum_height=max(280, self.modal_owner.height() - 48),
            restart=restart,
            parent=self.widget,
        )
        self.widget.setFixedWidth(self.content.width())
        self.widget.setMaximumHeight(self.content.maximumHeight())
        self.viewLayout.addWidget(self.content)
        self.content.dismissed.connect(self.accept)
        self.content.size_changed.connect(self._sync_content_geometry)
        self._sync_content_geometry()

    def _sync_content_geometry(self) -> None:
        """Keep changing report content centered within its fixed modal mask."""

        self.vBoxLayout.invalidate()
        self.vBoxLayout.activate()
        self.widget.adjustSize()
        self.widget.move(
            max(0, (self.width() - self.widget.width()) // 2),
            max(0, (self.height() - self.widget.height()) // 2),
        )
