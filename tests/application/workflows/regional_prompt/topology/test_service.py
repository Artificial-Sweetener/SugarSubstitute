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

"""Verify regional prompt topology resolves graph-bound prompt identities."""

from __future__ import annotations

from substitute.application.workflows.regional_prompt_topology_service import (
    RegionalPromptTopologyService,
)
from tests.application.workflows.regional_prompt.support import build_workflow


def test_topology_resolves_prompt_nodes_to_mask_endpoint() -> None:
    """Resolve positive and negative prompt identity through shared graph topology."""

    workflow = build_workflow("global\n[SEP]\nfirst", mask_count=1)
    service = RegionalPromptTopologyService()

    topology = service.topology_for_prompt(workflow, "Region", "positive")

    assert topology is not None
    assert topology.association_key == ("Region", "masks")
    assert topology.prompt_node_names == ("positive", "negative")
    assert service.topology_for_mask(workflow, ("Region", "masks")) == topology
