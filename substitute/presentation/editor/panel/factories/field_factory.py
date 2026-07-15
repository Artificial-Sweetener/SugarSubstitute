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

"""Define the common editor field factory request and factory protocol."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

EditorFieldFactoryResult = object | None
EditorWidgetFactory = Callable[..., EditorFieldFactoryResult]


@dataclass(frozen=True, slots=True)
class EditorFieldBuildRequest:
    """Carry prepared field metadata and injected services to field factories."""

    parent: object
    node_name: str
    key: str
    value: object
    field_meta: dict[str, object]
    node_definition_gateway: object | None = None
    node_type: object | None = None
    field_type: object | None = None
    field_info: object | None = None
    constraints: dict[str, object] = field(default_factory=dict)
    extra_kwargs: Mapping[str, object] = field(default_factory=dict)

    def callable_kwargs(self) -> dict[str, object]:
        """Return injected keyword arguments for callable field factories."""

        kwargs = dict(self.extra_kwargs)
        kwargs["node_definition_gateway"] = self.node_definition_gateway
        kwargs.setdefault("node_type", self.node_type)
        kwargs.setdefault("field_type", self.field_type)
        kwargs.setdefault("field_info", self.field_info)
        kwargs.setdefault("constraints", self.constraints)
        return kwargs


class EditorFieldFactory(Protocol):
    """Build one editor field widget from a prepared field request."""

    def build_field_widget(
        self, request: EditorFieldBuildRequest
    ) -> EditorFieldFactoryResult:
        """Return a widget, layout sentinel, or None when this factory declines."""
        ...


@dataclass(frozen=True, slots=True)
class CallableEditorFieldFactory:
    """Adapt a callable field factory signature to the request protocol."""

    factory: EditorWidgetFactory

    def build_field_widget(
        self, request: EditorFieldBuildRequest
    ) -> EditorFieldFactoryResult:
        """Invoke the wrapped callable with the panel field positional contract."""

        return self.factory(
            request.parent,
            request.node_name,
            request.key,
            request.value,
            request.field_meta,
            **request.callable_kwargs(),
        )
