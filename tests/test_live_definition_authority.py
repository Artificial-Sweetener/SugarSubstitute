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

"""Tests for live-only Comfy node-definition authority."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from substitute.application.node_behavior import (
    LiveNodeDefinitionAuthority,
    LiveNodeDefinitionError,
    extract_live_list_options,
)


class _Gateway:
    """Return deterministic Comfy object-info payloads for tests."""

    def __init__(self, payloads: Mapping[str, object]) -> None:
        """Store payloads keyed by requested node class."""

        self._payloads = dict(payloads)

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one object-info payload."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one required object-info payload."""

        payload = self._payloads.get(node_class, {})
        return dict(payload) if isinstance(payload, Mapping) else {}


def test_authority_returns_direct_live_field_definition() -> None:
    """Required fields should be resolved from live Comfy payloads."""

    authority = LiveNodeDefinitionAuthority(
        _Gateway(
            {
                "SamplerNode": {
                    "SamplerNode": {
                        "input": {
                            "required": {
                                "sampler_name": [
                                    ["euler", "euler_ancestral"],
                                    {"tooltip": "Sampler choice."},
                                ]
                            }
                        }
                    }
                }
            }
        )
    )

    field = authority.get_required_field(
        "SamplerNode",
        "sampler_name",
        operation="test",
    )

    assert field.field_type == "LIST"
    assert field.meta_info == {"tooltip": "Sampler choice."}
    assert extract_live_list_options(field.field_info) == (
        "euler",
        "euler_ancestral",
    )


def test_authority_raises_when_payload_is_empty() -> None:
    """Empty Comfy payloads should be blocking definition failures."""

    authority = LiveNodeDefinitionAuthority(_Gateway({}))

    with pytest.raises(LiveNodeDefinitionError) as error_info:
        authority.get_required_definition("MissingNode", operation="test")

    error = error_info.value
    assert error.missing_definitions[0].class_type == "MissingNode"
    assert "MissingNode" in str(error)


def test_authority_raises_when_payload_lacks_requested_class() -> None:
    """Object-info payloads must contain the exact requested class key."""

    authority = LiveNodeDefinitionAuthority(
        _Gateway({"RequestedNode": {"OtherNode": {"input": {}}}})
    )

    with pytest.raises(LiveNodeDefinitionError) as error_info:
        authority.get_required_definition("RequestedNode", operation="test")

    assert error_info.value.missing_definitions[0].class_type == "RequestedNode"


def test_authority_returns_no_tooltip_when_live_metadata_lacks_tooltip() -> None:
    """Missing live tooltip metadata should not synthesize tooltip text."""

    authority = LiveNodeDefinitionAuthority(
        _Gateway(
            {
                "SamplerNode": {
                    "SamplerNode": {
                        "input": {"required": {"scheduler": [["normal"], {}]}}
                    }
                }
            }
        )
    )

    field = authority.get_required_field(
        "SamplerNode",
        "scheduler",
        operation="test",
    )

    assert "tooltip" not in field.meta_info


def test_authority_ignores_external_cube_metadata_by_construction() -> None:
    """Only the gateway payload can influence resolved field metadata."""

    cube_metadata = {"tooltip": "Cube-authored tooltip", "options": ["cube_only"]}
    authority = LiveNodeDefinitionAuthority(
        _Gateway(
            {
                "SamplerNode": {
                    "SamplerNode": {
                        "input": {
                            "required": {
                                "sampler_name": [["euler"], {"tooltip": "Live"}]
                            }
                        }
                    }
                }
            }
        )
    )

    field = authority.get_required_field(
        "SamplerNode",
        "sampler_name",
        operation="test",
    )

    assert cube_metadata["tooltip"] not in field.meta_info.values()
    assert extract_live_list_options(field.field_info) == ("euler",)
