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

"""Verify regional keyboard reorder preview composition through the real shell."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from tests.support.prompt_editor.real_shell.reorder_rendering import (
    capture_reorder_layout,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_alt_up_preview_preserves_regional_settled_layout(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep a moved chip on the same regional-chrome side as its commit."""

    initial_text = (
        "best quality, score_7, masterpiece, very aesthetic, full body, "
        "dramatic angle, dusk,"
        "\n\n1girl, (wind:2.00), petite, looking away, facing away, mature female, "
        "(leaning on weapon:2.00), (holding staff:1.60), large wooden staff, "
        "crook mage staff, large crook, (flat chest:2.00), small breasts,"
        "\n\n(wind lift, floating hair, hat lift, skirt lift:3.00), purple petals, "
        "(hand on own hat, ribbon lift:3.00), fighting stance, holding down headwear, "
        "hand on headwear,"
        "\n[SEP]\npink witch hat, slim, pigeon-toed, falling petals,"
        "\n\ndetermined, narrowed eyes, threat, fang, shaded face, hair ribbon, "
        "swept bangs, blue ribbon trim,"
        "\n\n(pink and blue:1.05) witch outfit, bare arms, magical girl, "
        "(blue accents:1.10), zettai ryouiki, pink corset, off shoulder, "
        "butterfly shaped bows, pink boots,"
        "\n\n(blue laces:1.50), blue ribbon, pink short skirt, pink petticoat, pink frills, "
        "blue frills, blue butterfly ornaments, (red:1.10) heart jewel ornaments, "
        "heart-shaped gem, heart jeweled collar, beautiful orange and purple sunset sky,  "
        "\n\npink hair, long hair, twintails, (hair between eyes:1.20), "
        "white frilled wrist cuffs, "
        "\n\nribbon-trimmed vertical-striped pink thighhighs, "
        "blue decorative staff bow ribbon, pink eyes, (blue:1.35) ribbon, "
        "(skindentaiton:1.40), (blue:1.10) bow, pink nails, collarbone,   "
        "\n\n[SEP]\ngrass, flower field, cloudy sky, pink petals, blue petals, "
        "mountainous horizon,    "
        "\n\nfloating red staff orb, <lora:Anima\\style\\MJBS_anima:1.00>"
    )
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=initial_text)
    field.editor.resize(800, 520)
    real_shell_scenario.wait_for_queued_delivery()
    real_shell_scenario.input.set_source_cursor_position(
        field,
        initial_text.index("pink witch hat") + 1,
    )
    editor = field.editor
    real_shell_scenario.input.focus_editor(field)

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    real_shell_scenario.wait_for_queued_delivery()
    QTest.keyPress(
        editor,
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.AltModifier,
    )
    real_shell_scenario.wait_for_queued_delivery()
    preview = capture_reorder_layout(field, label="regional-alt-up-preview")

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    real_shell_scenario.wait_until(
        lambda: (
            cast(Any, editor)._surface._reorder_preview_projection.preview_frame is None
        )
    )
    real_shell_scenario.wait_for_queued_delivery()
    settled = capture_reorder_layout(field, label="regional-alt-up-settled")

    assert preview.preview_active
    assert not settled.preview_active
    assert preview.source_text == settled.source_text
    assert preview.projection_text == settled.projection_text
    assert preview.line_rects == settled.line_rects
    assert preview.fragments == settled.fragments
    assert preview.region_divider_lines == settled.region_divider_lines
    assert preview.region_rail_lines == settled.region_rail_lines
