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

"""Verify regional prompt validation against ordered mask availability."""

from __future__ import annotations

from substitute.application.workflows.regional_prompt_validation_service import (
    RegionalPromptValidationService,
)
from tests.application.workflows.regional_prompt.support import build_workflow


def test_regional_prompt_validation_blocks_prompt_regions_without_masks() -> None:
    """Each regional prompt partition must have a materialized ordered mask."""

    issues = RegionalPromptValidationService().validate(
        build_workflow("global\n[SEP]\nfirst\n[SEP|Second]\nsecond", mask_count=1)
    )

    assert len(issues) == 1
    assert issues[0].association_key == ("Region", "masks")
    assert issues[0].required_region_count == 2
    assert issues[0].available_mask_count == 1


def test_regional_prompt_validation_allows_extra_editable_masks() -> None:
    """Extra masks should remain editable and should not block generation."""

    assert (
        RegionalPromptValidationService().validate(
            build_workflow("global\n[SEP]\nfirst", mask_count=3)
        )
        == ()
    )
