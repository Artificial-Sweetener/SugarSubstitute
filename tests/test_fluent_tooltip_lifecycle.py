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

"""Verify Fluent tooltip filters cannot retain deleted floating-window children."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    FluentToolTipFilter,
    release_fluent_tooltips,
    set_fluent_tooltip_text,
)


class _Tooltip:
    """Record the hide operation expected before an ancestor window closes."""

    def __init__(self) -> None:
        """Initialize visible semantic state."""

        self.hidden = False

    def hide(self) -> None:
        """Record Fluent's public hide call."""

        self.hidden = True


def test_release_fluent_tooltips_invalidates_surviving_filter_window() -> None:
    """A redocked control should create a new tooltip in its new window."""

    _application = QApplication.instance() or QApplication([])
    control = QWidget()
    set_fluent_tooltip_text(control, "Tooltip")
    tooltip_filter = control.findChild(FluentToolTipFilter)
    assert tooltip_filter is not None
    tooltip = _Tooltip()
    setattr(tooltip_filter, "_tooltip", tooltip)

    release_fluent_tooltips(control)

    assert tooltip.hidden
    assert getattr(tooltip_filter, "_tooltip", None) is None
    control.deleteLater()
