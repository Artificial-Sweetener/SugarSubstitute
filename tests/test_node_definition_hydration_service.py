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

"""Contract tests for editor node-definition hydration orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from substitute.application.node_behavior import (
    EditorNodeDefinitionHydrationService,
    LiveNodeDefinitionError,
)
from substitute.application.ports import NodeDefinitionHydrationResult


@dataclass(frozen=True)
class _CubeState:
    """Provide the buffer attribute required by the hydration service."""

    buffer: dict[str, object]


class _Hydrator:
    """Record foreground hydration requests from the service."""

    def __init__(self) -> None:
        """Initialize recorded request storage."""

        self.requests: list[tuple[str, ...]] = []

    def ensure_node_definitions(
        self,
        node_classes: Sequence[str],
    ) -> NodeDefinitionHydrationResult:
        """Record requested classes and report them available."""

        requested = tuple(node_classes)
        self.requests.append(requested)
        return NodeDefinitionHydrationResult(
            requested=requested,
            available=requested,
            unavailable=(),
        )


def test_hydration_service_collects_direct_and_wrapper_body_node_classes() -> None:
    """Hydration should request projection classes before widgets are built."""

    wrapper_id = "de2c84e5-02a8-4c50-831d-3c169dee4820"
    hydrator = _Hydrator()
    service = EditorNodeDefinitionHydrationService(hydrator)
    cube = _CubeState(
        buffer={
            "nodes": {
                "sampler": {"class_type": "KSampler"},
                "resize": {"class_type": wrapper_id},
            },
            "subgraphs": [
                {
                    "id": wrapper_id,
                    "name": "Resize",
                    "inputNode": {"id": -10},
                    "inputs": [
                        {
                            "name": "sampling",
                            "label": "Sampling",
                            "type": "COMBO",
                            "linkIds": [11],
                        },
                    ],
                    "outputs": [],
                    "links": [
                        [11, -10, 0, 42, 0, "COMBO"],
                    ],
                    "nodes": [
                        {
                            "id": 42,
                            "type": "SimpleSyrup.ResizeImageToTarget",
                            "inputs": [
                                {
                                    "name": "sampling",
                                    "type": "COMBO",
                                    "widget": {"name": "sampling"},
                                    "link": 11,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    result = service.hydrate_for_projection(
        cube_states={"A": cube},
        stack_order=["A"],
    )

    assert result is not None
    assert hydrator.requests == [
        ("KSampler", "SimpleSyrup.ResizeImageToTarget"),
    ]
    assert result.available == ("KSampler", "SimpleSyrup.ResizeImageToTarget")


def test_hydration_service_raises_when_gateway_has_no_foreground_port() -> None:
    """Required definitions should block when foreground hydration is unavailable."""

    service = EditorNodeDefinitionHydrationService(object())

    with pytest.raises(LiveNodeDefinitionError) as error_info:
        service.hydrate_for_projection(
            cube_states={
                "A": _CubeState(
                    buffer={"nodes": {"sampler": {"class_type": "KSampler"}}}
                )
            },
            stack_order=["A"],
        )

    assert error_info.value.missing_definitions[0].class_type == "KSampler"
    assert error_info.value.missing_definitions[0].cube_aliases == ("A",)
    assert error_info.value.missing_definitions[0].node_names == ("sampler",)


def test_hydration_service_skips_empty_projection_without_foreground_port() -> None:
    """Empty projections should not require foreground definition hydration."""

    service = EditorNodeDefinitionHydrationService(object())

    result = service.hydrate_for_projection(
        cube_states={"A": _CubeState(buffer={"nodes": {}})},
        stack_order=["A"],
    )

    assert result is None


def test_hydration_service_raises_for_unavailable_classes() -> None:
    """Unavailable foreground hydration results should become blocking errors."""

    class _UnavailableHydrator:
        """Report requested node classes as unavailable."""

        def ensure_node_definitions(
            self,
            node_classes: Sequence[str],
        ) -> NodeDefinitionHydrationResult:
            """Return an unavailable result for every requested class."""

            requested = tuple(node_classes)
            return NodeDefinitionHydrationResult(
                requested=requested,
                available=(),
                unavailable=requested,
            )

    service = EditorNodeDefinitionHydrationService(_UnavailableHydrator())

    with pytest.raises(LiveNodeDefinitionError) as error_info:
        service.hydrate_for_projection(
            cube_states={
                "A": _CubeState(
                    buffer={"nodes": {"sampler": {"class_type": "KSampler"}}}
                )
            },
            stack_order=["A"],
        )

    assert error_info.value.missing_definitions[0].class_type == "KSampler"
    assert error_info.value.missing_definitions[0].cube_aliases == ("A",)
    assert error_info.value.missing_definitions[0].node_names == ("sampler",)


def test_hydration_service_attributes_same_missing_class_to_each_cube() -> None:
    """Unavailable classes used by multiple cubes should keep cube ownership."""

    class _UnavailableHydrator:
        """Report requested node classes as unavailable."""

        def ensure_node_definitions(
            self,
            node_classes: Sequence[str],
        ) -> NodeDefinitionHydrationResult:
            """Return an unavailable result for every requested class."""

            requested = tuple(node_classes)
            return NodeDefinitionHydrationResult(
                requested=requested,
                available=(),
                unavailable=requested,
            )

    service = EditorNodeDefinitionHydrationService(_UnavailableHydrator())

    with pytest.raises(LiveNodeDefinitionError) as error_info:
        service.hydrate_for_projection(
            cube_states={
                "A": _CubeState(
                    buffer={"nodes": {"sampler_a": {"class_type": "KSampler"}}}
                ),
                "B": _CubeState(
                    buffer={"nodes": {"sampler_b": {"class_type": "KSampler"}}}
                ),
            },
            stack_order=["A", "B"],
        )

    missing = error_info.value.missing_definitions
    assert tuple(item.class_type for item in missing) == ("KSampler", "KSampler")
    assert tuple(item.cube_aliases for item in missing) == (("A",), ("B",))
    assert tuple(item.node_names for item in missing) == (
        ("sampler_a",),
        ("sampler_b",),
    )


def test_hydration_skips_frontend_value_proxy_and_tolerates_local_fallback() -> None:
    """Local workflow schemas should render without backend-only UI node classes."""

    class _UnavailableHydrator:
        """Record optional enrichment and report it unavailable."""

        def __init__(self) -> None:
            self.requests: list[tuple[str, ...]] = []

        def ensure_node_definitions(
            self,
            node_classes: Sequence[str],
        ) -> NodeDefinitionHydrationResult:
            requested = tuple(node_classes)
            self.requests.append(requested)
            return NodeDefinitionHydrationResult(
                requested=requested,
                available=(),
                unavailable=requested,
            )

    hydrator = _UnavailableHydrator()
    service = EditorNodeDefinitionHydrationService(hydrator)
    result = service.hydrate_for_projection(
        cube_states={
            "A": _CubeState(
                buffer={
                    "nodes": {
                        "45": {
                            "class_type": "PrimitiveNode",
                            "inputs": {"steps": 25},
                            "_workflow": {
                                "execution_role": "value_proxy",
                                "editor_definition": {
                                    "input": {
                                        "required": {"steps": ["INT", {"default": 25}]}
                                    }
                                },
                            },
                        },
                        "7": {
                            "class_type": "MissingCustomNode",
                            "inputs": {"amount": 0.75},
                            "_workflow": {
                                "execution_role": "executable",
                                "editor_definition": {
                                    "input": {
                                        "required": {
                                            "amount": ["FLOAT", {"default": 0.75}]
                                        }
                                    }
                                },
                            },
                        },
                    }
                }
            )
        },
        stack_order=["A"],
    )

    assert result is not None
    assert hydrator.requests == [("MissingCustomNode",)]
    assert result.unavailable == ("MissingCustomNode",)
