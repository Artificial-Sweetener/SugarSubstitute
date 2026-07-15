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

"""Select editor field factories from prepared field build requests."""

from __future__ import annotations

from collections.abc import Iterable

from substitute.presentation.editor.panel.factories.field_factory import (
    CallableEditorFieldFactory,
    EditorFieldBuildRequest,
    EditorFieldFactory,
    EditorFieldFactoryResult,
    EditorWidgetFactory,
)


class EditorFieldFactoryRegistry:
    """Maintain ordered field factories and select the first matching result."""

    def __init__(self, factories: Iterable[EditorFieldFactory] = ()) -> None:
        """Store initial factories in evaluation order."""

        self._factories: list[EditorFieldFactory] = list(factories)

    def register(self, factory: EditorFieldFactory) -> EditorFieldFactory:
        """Append one request-based factory and return it for decorator use."""

        self._factories.append(factory)
        return factory

    def register_callable_factory(
        self, factory: EditorWidgetFactory
    ) -> EditorWidgetFactory:
        """Append one existing callable factory through the protocol adapter."""

        self._factories.append(CallableEditorFieldFactory(factory))
        return factory

    def registered_factories(self) -> tuple[EditorFieldFactory, ...]:
        """Return registered request factories in evaluation order."""

        return tuple(self._factories)

    def build_widget(
        self, request: EditorFieldBuildRequest
    ) -> EditorFieldFactoryResult:
        """Return the first non-None field result from registered factories."""

        for factory in self._factories:
            result = factory.build_field_widget(request)
            if result is not None:
                return result
        return None
