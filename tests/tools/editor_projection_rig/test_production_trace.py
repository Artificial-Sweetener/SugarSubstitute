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

"""Contract tests for the editor projection optimization rig."""

from __future__ import annotations

from tools.editor_projection_rig.production_trace import (
    _budget_summary,
    _partial_orphan_field_card_refs,
)


def test_production_trace_flags_orphaned_field_widgets_as_correctness_failure() -> None:
    """A missing card wrapper with registered fields must fail production budgets."""

    signature = {
        "cube_sections": [
            {
                "alias": "Cube 3: SDXL/Automask Detailer",
                "node_cards": [
                    {
                        "node_name": "detailer",
                        "visible": False,
                        "fields": [
                            {"field_key": "steps", "visible": True},
                            {"field_key": "model", "visible": False},
                        ],
                    }
                ],
            }
        ]
    }

    refs = _partial_orphan_field_card_refs(signature)
    budgets = _budget_summary(
        [
            {
                "projection_completed": True,
                "signature_matched": True,
                "parent_chain_violations": [],
                "partial_orphan_field_cards": refs,
            }
        ]
    )

    assert refs == ["Cube 3: SDXL/Automask Detailer:detailer"]
    assert budgets["partial_orphan_field_cards"]["actual"] == 1
    assert budgets["partial_orphan_field_cards"]["passed"] is False
