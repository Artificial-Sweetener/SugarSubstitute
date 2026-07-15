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

"""Manage projected widget visibility during staged editor builds."""

from __future__ import annotations


def prepare_projected_widget_for_hidden_build(widget: object) -> None:
    """Keep a staged cube section non-visible while its card subtree is assembled."""

    call_widget_bool_method(widget, "setUpdatesEnabled", False)
    hide = getattr(widget, "hide", None)
    if callable(hide):
        hide()
        return
    call_widget_bool_method(widget, "setVisible", False)


def call_widget_bool_method(widget: object, method_name: str, value: bool) -> None:
    """Call a one-argument widget boolean method when the object supports it."""

    method = getattr(widget, method_name, None)
    if callable(method):
        method(value)
