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

"""Verify regional prompt label derivation for ordered mask entries."""

from __future__ import annotations

from substitute.application.workflows.regional_prompt_label_service import (
    RegionalPromptLabelService,
)
from tests.application.workflows.regional_prompt.support import build_workflow


def test_labels_follow_authored_sep_names_in_mask_order() -> None:
    """Prefer the first authored region name across related prompts."""

    workflow = build_workflow(
        "global\n[SEP|Character]\nfirst\n[SEP]\nsecond",
        mask_count=3,
    )

    labels = RegionalPromptLabelService().labels_for_mask(
        workflow,
        ("Region", "masks"),
        region_count=3,
    )

    assert labels == ("Character", None, None)


def test_labels_accept_current_editor_text_before_graph_commit() -> None:
    """Use the changed prompt source snapshot for live panel projection."""

    workflow = build_workflow("global\n[SEP|Old]\nfirst", mask_count=1)

    labels = RegionalPromptLabelService().labels_for_mask(
        workflow,
        ("Region", "masks"),
        region_count=1,
        prompt_text_overrides={"positive": "global\n[SEP|New]\nfirst"},
    )

    assert labels == ("New",)
