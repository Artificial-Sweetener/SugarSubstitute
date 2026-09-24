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

"""Characterize the shared result contract across prompt mutation families."""

from __future__ import annotations

from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget


def test_prompt_mutation_families_publish_consistent_editor_state() -> None:
    """Every mutation family should return matching text, selection, and semantics."""

    mutation_service = PromptMutationService()
    lora_text = "<lora:Mineru:0.8>"
    mutations = (
        mutation_service.adjust_emphasis(
            "cat",
            selection_start=0,
            selection_end=3,
            delta=0.05,
        ),
        mutation_service.set_lora_weight_for_outer_range(
            lora_text,
            outer_start=0,
            outer_end=len(lora_text),
            weight=1.25,
        ),
        mutation_service.set_wildcard_tag_for_outer_range(
            "{monster}",
            outer_start=0,
            outer_end=9,
            tag="2",
        ),
        mutation_service.reorder_chips(
            "alpha,beta",
            dragged_chip_index=1,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
        ),
    )

    assert all(mutation is not None for mutation in mutations)
    assert tuple(
        (
            mutation.text,
            mutation.selection_start,
            mutation.selection_end,
            mutation.document_view.source_text,
        )
        for mutation in mutations
        if mutation is not None
    ) == (
        ("(cat:1.05)", 1, 4, "(cat:1.05)"),
        ("<lora:Mineru:1.25>", 13, 17, "<lora:Mineru:1.25>"),
        ("{monster|2}", 10, 10, "{monster|2}"),
        ("beta, alpha", 0, 4, "beta, alpha"),
    )
