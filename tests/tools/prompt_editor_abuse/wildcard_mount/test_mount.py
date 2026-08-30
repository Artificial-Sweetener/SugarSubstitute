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

"""Verify isolated lifecycle ownership for wildcard abuse editor mounts."""

from __future__ import annotations

from pathlib import Path

from shiboken6 import isValid

from tools.prompt_editor_abuse.wildcard_mount import mount_wildcard_editor
from tools.prompt_editor_abuse.workloads import hostile_prompt_scenarios


def test_wildcard_abuse_mount_destroys_generated_modal_owner(tmp_path: Path) -> None:
    """Closing one harness mount should destroy its complete temporary widget tree."""

    scenario = next(
        scenario
        for scenario in hostile_prompt_scenarios()
        if scenario.name == "wildcard-pointer-drag-autoscroll"
    )
    with mount_wildcard_editor(scenario, artifact_root=tmp_path) as mounted:
        modal = mounted.modal
        owner = mounted.owner
        controls = mounted.editor._token_weight_control_overlay

    assert not isValid(modal)
    assert owner is not None
    assert not isValid(owner)
    assert not isValid(controls)


def test_wildcard_abuse_mount_applies_scenario_editor_size(tmp_path: Path) -> None:
    """Mount wildcard scenarios with their requested hostile viewport geometry."""

    scenario = next(
        scenario
        for scenario in hostile_prompt_scenarios()
        if scenario.name == "wildcard-pointer-drag-autoscroll"
    )

    with mount_wildcard_editor(scenario, artifact_root=tmp_path) as mounted:
        editor_size = mounted.editor.size()

    assert (editor_size.width(), editor_size.height()) == scenario.viewport_size
