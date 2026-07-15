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

"""Application-layer adapter for editor control registry access."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

RegisteredWidgetBuilder = Callable[..., Any]
WidgetBuilderLookup = Callable[[str], RegisteredWidgetBuilder | None]
BuiltinControlRegistrar = Callable[
    [
        Callable[[object, object, float, float, float], object],
        Callable[[object, object, int, int, int], object],
        Callable[..., object],
    ],
    None,
]

_widget_builder_lookup: WidgetBuilderLookup | None = None
_builtin_control_registrar: BuiltinControlRegistrar | None = None


def configure_control_registry_service(
    *,
    widget_builder_lookup: WidgetBuilderLookup,
    builtin_control_registrar: BuiltinControlRegistrar,
) -> None:
    """Bind infrastructure registry adapters at bootstrap composition boundary."""

    global _widget_builder_lookup, _builtin_control_registrar
    _widget_builder_lookup = widget_builder_lookup
    _builtin_control_registrar = builtin_control_registrar


def _require_widget_builder_lookup() -> WidgetBuilderLookup:
    """Return configured builder lookup adapter or fail fast when unbound."""

    if _widget_builder_lookup is None:
        raise RuntimeError("Control registry service is not configured.")
    return _widget_builder_lookup


def _require_builtin_control_registrar() -> BuiltinControlRegistrar:
    """Return configured builtin registrar adapter or fail fast when unbound."""

    if _builtin_control_registrar is None:
        raise RuntimeError("Control registry service is not configured.")
    return _builtin_control_registrar


def get_registered_widget_builder(control: str) -> Callable[..., Any] | None:
    """Return a registered editor widget builder for a control key."""

    return _require_widget_builder_lookup()(control)


def register_editor_control_builders(
    float_builder: Callable[[object, object, float, float, float], object],
    int_builder: Callable[[object, object, int, int, int], object],
    color_builder: Callable[..., object],
) -> None:
    """Register presentation-provided builtins in the control registry."""

    _require_builtin_control_registrar()(float_builder, int_builder, color_builder)


__all__ = [
    "configure_control_registry_service",
    "get_registered_widget_builder",
    "register_editor_control_builders",
]
