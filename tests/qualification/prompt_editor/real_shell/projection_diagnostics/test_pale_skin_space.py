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

"""Verify projection stability for the reported pale-skin space edit."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)
from tests.support.prompt_editor.projection_surface_support import (
    RecordingThumbnailAssetRepository,
    StaticPromptLoraCatalog,
    lora_catalog_item_with_banner,
)


def test_real_shell_keeps_pale_skin_space_edit_layout_stable(tmp_path: Path) -> None:
    """Keep the reported narrow prompt space edit from moving stable rows."""

    prompt_name = r"Anima\style\People'sWorks_v10_Animabasev1.0_test3-000008"
    prompt = "\n".join(
        (
            "best quality, score_7, ppw, masterpiece, very aesthetic, "
            "character portrait, faux figurine, garden,",
            "1girl, (mature female:1.10), floating, parted lips, contrapposto, "
            "holding helix spear, planted spear, skinny,",
            "(small:1.20) breasts, flat chest, sparkling blue sash, "
            "sparkling blue bralette,",
            "(pale skin:1.20),",
            "backpack basket, pointy ears, sharp teeth, too many rabbits, "
            "backlighting,",
            "empty eyes, sharp teeth, too many rabbits, backlighting,",
            "white dress, wrathful, pink bridal garter, sparkling dress,",
            "glowing red eyes, long white hair, swept bangs, elegant seductive pose, "
            "twintails, white eyebrows, pink hair ribbon, see-through dress, "
            "iridescent belt, spaghetti strap, short white oni horns,",
            "convenient censoring, barefoot, cloudy sky, blue sky, golden hour, "
            "night sky, column, black and white roses, halo behind head,",
            f"<lora:{prompt_name}:1.00>",
        )
    )
    thumbnail_repository = RecordingThumbnailAssetRepository()
    real_shell_scenario = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(prompt_name=prompt_name),)
        ),
        thumbnail_asset_repository=thumbnail_repository,
    )
    try:
        field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=prompt)
        real_shell_scenario.shell.resize(412, 1300)
        panel = real_shell_scenario.shell.editor_panels[field.workflow.workflow_id]
        panel.setMinimumWidth(412)
        panel.resize(412, 1220)
        field.editor.setManualScrollHeight(1200)
        real_shell_scenario.wait_for_queued_delivery()
        insertion_position = prompt.index("(pale skin:1.20),") + len(
            "(pale skin:1.20),"
        )
        cursor = field.editor.textCursor()
        cursor.setPosition(insertion_position)
        field.editor.setTextCursor(cursor)
        real_shell_scenario.input.focus_editor(field)
        before = real_shell_scenario.snapshots.capture(field, label="before-pale-space")

        real_shell_scenario.input.press_key(field, Qt.Key.Key_Space)

        after = real_shell_scenario.snapshots.capture(field, label="after-pale-space")
        violations = transition_violations(
            action_name="space",
            before=before,
            after=after,
            snapshot_violations=snapshot_invariant_violations,
        )
    finally:
        real_shell_scenario.close()

    assert thumbnail_repository.reads
    assert after.source_text[insertion_position : insertion_position + 2] == " \n"
    assert before.layout_line_count == after.layout_line_count
    assert before.layout_content_height == after.layout_content_height
    assert not [
        violation
        for violation in violations
        if "height_shift" in violation
        or "geometry_shift" in violation
        or "visible_row_shift" in violation
        or "visible_fragment_shift" in violation
    ]
