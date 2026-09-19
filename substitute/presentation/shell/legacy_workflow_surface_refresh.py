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

"""Adapt legacy shell surface refresh callbacks at one compatibility boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from inspect import Parameter, signature


def call_legacy_surface_refresh(
    legacy_refresh: Callable[..., object],
    *,
    force_refresh: bool,
    on_complete: Callable[[], None] | None,
) -> None:
    """Call a legacy refresh hook using only the options it accepts."""

    parameters: Mapping[str, Parameter]
    try:
        parameters = signature(legacy_refresh).parameters
    except (TypeError, ValueError):
        parameters = {}
    supports_variadic_keywords = any(
        parameter.kind is Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    supports_force_refresh = "force_refresh" in parameters or supports_variadic_keywords
    supports_on_complete = "on_complete" in parameters or supports_variadic_keywords
    kwargs: dict[str, object] = {}
    if supports_force_refresh:
        kwargs["force_refresh"] = force_refresh
    if supports_on_complete:
        kwargs["on_complete"] = on_complete
    legacy_refresh(**kwargs)
    if on_complete is not None and not supports_on_complete:
        on_complete()


__all__ = ["call_legacy_surface_refresh"]
