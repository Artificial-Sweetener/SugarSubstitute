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

"""Publish stable Qt identity for rendered global-override surfaces."""

from __future__ import annotations

OVERRIDE_KEY_PROPERTY = "substitute_override_key"
OVERRIDE_ROLE_PROPERTY = "substitute_override_role"
OVERRIDE_CONTROL_ROLE = "control"
OVERRIDE_LABEL_ROLE = "label"


def identify_override_surface(
    *,
    override_key: str,
    label_widget: object,
    control_widget: object,
) -> None:
    """Expose semantic identity on Qt surfaces while permitting factory doubles."""

    _identify_surface(label_widget, override_key, OVERRIDE_LABEL_ROLE)
    _identify_surface(control_widget, override_key, OVERRIDE_CONTROL_ROLE)


def _identify_surface(surface: object, override_key: str, role: str) -> None:
    """Publish identity when a rendered surface exposes Qt dynamic properties."""

    set_property = getattr(surface, "setProperty", None)
    if not callable(set_property):
        return
    set_property(OVERRIDE_KEY_PROPERTY, override_key)
    set_property(OVERRIDE_ROLE_PROPERTY, role)


__all__ = [
    "OVERRIDE_CONTROL_ROLE",
    "OVERRIDE_KEY_PROPERTY",
    "OVERRIDE_LABEL_ROLE",
    "OVERRIDE_ROLE_PROPERTY",
    "identify_override_surface",
]
