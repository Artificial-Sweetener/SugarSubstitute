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

"""Behavior snapshot observability contracts."""

from __future__ import annotations

import logging

import pytest

from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from tests.support.node_behavior import (
    DummyNodeDefinitionGateway,
    cube_state,
)


def test_build_snapshot_keeps_definition_resolution_details_out_of_info_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Normal behavior snapshots should log summaries without per-node detail spam."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {"KSampler": {"input": {"required": {"seed": ["INT", {}]}}}}
        )
    )
    cubes = {
        "A": cube_state(
            nodes={
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {"seed": 7},
                }
            },
            definitions={
                "KSampler": {"input": {"required": {"seed": ["INT", {}]}}},
            },
        )
    }

    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.application.node_behavior.behavior_service",
    )
    service.build_snapshot(cube_states=cubes, stack_order=["A"])

    assert "Built editor behavior snapshot" in caplog.text
    assert "Resolved node definition from live and cube metadata" not in caplog.text
    assert "Resolved empty node definition" not in caplog.text
