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

"""Contract tests for the panel field factory registry boundary."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from substitute.application.ports import (
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.node_behavior import FieldBehavior
from substitute.presentation.editor.panel.factories.field_factory import (
    EditorFieldBuildRequest,
)
import substitute.presentation.editor.panel.factories.field_pipeline as field_pipeline
from substitute.presentation.editor.panel.factories.registry import (
    EditorFieldFactoryRegistry,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


class _DecliningFactory:
    """Record requests while declining to build a widget."""

    def __init__(self) -> None:
        """Initialize the captured request list."""

        self.requests: list[EditorFieldBuildRequest] = []

    def build_field_widget(self, request: EditorFieldBuildRequest) -> object | None:
        """Record one request and decline it."""

        self.requests.append(request)
        return None


class _ReturningFactory:
    """Record requests and return a configured widget marker."""

    def __init__(self, marker: object) -> None:
        """Store the marker returned for handled fields."""

        self.marker = marker
        self.requests: list[EditorFieldBuildRequest] = []

    def build_field_widget(self, request: EditorFieldBuildRequest) -> object | None:
        """Record one request and return the configured marker."""

        self.requests.append(request)
        return self.marker


def test_field_factory_registry_returns_first_non_none_result() -> None:
    """The registry should preserve order and stop after the first handled field."""

    marker = object()
    declining_factory = _DecliningFactory()
    returning_factory = _ReturningFactory(marker)
    skipped_factory = _ReturningFactory(object())
    registry = EditorFieldFactoryRegistry(
        (declining_factory, returning_factory, skipped_factory)
    )
    request = EditorFieldBuildRequest(
        parent=object(),
        node_name="Node",
        key="field",
        value="value",
        field_meta={},
    )

    assert registry.build_widget(request) is marker
    assert declining_factory.requests == [request]
    assert returning_factory.requests == [request]
    assert skipped_factory.requests == []


def test_callable_factory_registration_preserves_field_call_signature() -> None:
    """Callable factories should receive the panel field positional and kwarg shape."""

    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    registry = EditorFieldFactoryRegistry()

    def _callable_factory(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return "callable-widget"

    assert registry.register_callable_factory(_callable_factory) is _callable_factory
    request = EditorFieldBuildRequest(
        parent="parent",
        node_name="Node",
        key="field",
        value=3,
        field_meta={"cube_alias": "cube"},
        node_definition_gateway="gateway",
        node_type="NodeType",
        field_type="INT",
        field_info={"default": 3},
        constraints={"min": 0},
        extra_kwargs={"custom": "service"},
    )

    assert registry.build_widget(request) == "callable-widget"
    assert calls == [
        (
            ("parent", "Node", "field", 3, {"cube_alias": "cube"}),
            {
                "custom": "service",
                "node_definition_gateway": "gateway",
                "node_type": "NodeType",
                "field_type": "INT",
                "field_info": {"default": 3},
                "constraints": {"min": 0},
            },
        )
    ]


def test_build_widget_for_field_behavior_routes_generic_fields_through_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The field pipeline should delegate generic fallback to the registry."""

    marker = object()
    captured_requests: list[EditorFieldBuildRequest] = []

    class _Registry:
        """Capture the generic fallback request from the field pipeline."""

        def build_widget(self, request: EditorFieldBuildRequest) -> object:
            """Return the marker while recording the request."""

            captured_requests.append(request)
            return marker

    monkeypatch.setattr(field_pipeline, "FIELD_FACTORY_REGISTRY", _Registry())

    result = field_pipeline.build_widget_for_field_behavior(
        parent=cast("QWidget", SimpleNamespace()),
        field_behavior=FieldBehavior(field_key="note"),
        node_name="ExampleNode",
        key="note",
        value="hello",
        field_meta={"cube_alias": "cube-a"},
        prompt_autocomplete_gateway=cast(PromptAutocompleteGateway, object()),
        prompt_wildcard_catalog_gateway=cast(PromptWildcardCatalogGateway, object()),
        node_definition_gateway=cast(NodeDefinitionGateway, "gateway"),
        node_type="ExampleNode",
        field_type="STRING",
        field_info={"default": "hello"},
        constraints={},
        injected_service="service",
    )

    assert result is marker
    assert len(captured_requests) == 1
    request = captured_requests[0]
    assert request.node_name == "ExampleNode"
    assert request.key == "note"
    assert request.value == "hello"
    assert request.field_meta == {"cube_alias": "cube-a"}
    assert request.node_definition_gateway == "gateway"
    assert request.node_type == "ExampleNode"
    assert request.field_type == "STRING"
    assert request.field_info == {"default": "hello"}
    assert request.constraints == {}
    assert request.extra_kwargs["injected_service"] == "service"
