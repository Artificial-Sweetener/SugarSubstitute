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

"""Verify generation seed values project onto every rendered owner surface."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QApplication

from substitute.presentation.widgets import SeedBox
from tests.presentation.editor.panel.overrides.rendered_state.support import (
    DeterministicSeedRandomizer,
    node_seed_value,
    override_seed_value,
    randomize_for_generation,
    render_harness,
)


def test_randomized_override_and_node_seeds_project_every_generation(
    qt_application_owner: QApplication,
) -> None:
    """Keep both SeedBox surfaces equal to authoritative generation values."""

    harness = render_harness(qt_application_owner)
    override_seed = cast(SeedBox, harness.toolbar_widget("seed"))
    try:
        harness.node_seed.setMode("fixed")
        override_seed.setMode("random")
        override_randomizer = DeterministicSeedRandomizer([101, 102])

        randomize_for_generation(harness, override_randomizer)
        assert override_seed_value(harness.workflow) == 101
        assert override_seed.value() == 101

        randomize_for_generation(harness, override_randomizer)
        assert override_seed_value(harness.workflow) == 102
        assert override_seed.value() == 102
        assert node_seed_value(harness.workflow) == 7
        assert harness.node_seed.value() == 7

        harness.node_seed.setMode("random")
        override_seed.setMode("fixed")
        harness.workflow.global_overrides.pop("seed")
        node_randomizer = DeterministicSeedRandomizer([201, 202])

        randomize_for_generation(harness, node_randomizer)
        assert node_seed_value(harness.workflow) == 201
        assert harness.node_seed.value() == 201

        randomize_for_generation(harness, node_randomizer)
        assert node_seed_value(harness.workflow) == 202
        assert harness.node_seed.value() == 202
    finally:
        harness.close()
