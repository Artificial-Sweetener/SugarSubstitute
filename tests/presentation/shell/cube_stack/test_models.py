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

"""Verify pure cube-stack presentation target and frame policy."""

from __future__ import annotations

import pytest

from substitute.domain.workflow import WorkflowDocumentKind
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_COMPACT_WIDTH,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.presentation.shell.cube_stack_presentation_models import (
    CubeStackPreference,
    CubeStackPresentationFrame,
    CubeStackPresentationInput,
    CubeStackPresentationMode,
    interpolate_cube_stack_frame,
    resolve_cube_stack_presentation_mode,
    target_frame_for_mode,
)


@pytest.mark.parametrize(
    ("document_kind", "preference", "leases", "expected"),
    (
        (
            WorkflowDocumentKind.CUBE_STACK,
            CubeStackPreference.EXPANDED,
            0,
            CubeStackPresentationMode.EXPANDED,
        ),
        (
            WorkflowDocumentKind.CUBE_STACK,
            CubeStackPreference.COMPACT,
            0,
            CubeStackPresentationMode.COMPACT,
        ),
        (
            WorkflowDocumentKind.CUBE_STACK,
            CubeStackPreference.COMPACT,
            1,
            CubeStackPresentationMode.EXPANDED,
        ),
        (
            WorkflowDocumentKind.DIRECT_COMFY,
            CubeStackPreference.EXPANDED,
            0,
            CubeStackPresentationMode.UNAVAILABLE,
        ),
        (
            WorkflowDocumentKind.DIRECT_COMFY,
            CubeStackPreference.COMPACT,
            2,
            CubeStackPresentationMode.UNAVAILABLE,
        ),
    ),
)
def test_target_policy_keeps_document_availability_authoritative(
    document_kind: WorkflowDocumentKind,
    preference: CubeStackPreference,
    leases: int,
    expected: CubeStackPresentationMode,
) -> None:
    """Direct documents should remain unavailable despite preference or leases."""

    assert (
        resolve_cube_stack_presentation_mode(
            CubeStackPresentationInput(
                document_kind=document_kind,
                preference=preference,
                temporary_expansion_count=leases,
            )
        )
        is expected
    )


def test_mode_targets_define_exact_stack_and_item_endpoints() -> None:
    """Visible and unavailable modes should map to stable endpoint geometry."""

    expanded = target_frame_for_mode(
        CubeStackPresentationMode.EXPANDED,
        hidden_item_preference=CubeStackPreference.EXPANDED,
    )
    compact = target_frame_for_mode(
        CubeStackPresentationMode.COMPACT,
        hidden_item_preference=CubeStackPreference.COMPACT,
    )
    unavailable = target_frame_for_mode(
        CubeStackPresentationMode.UNAVAILABLE,
        hidden_item_preference=CubeStackPreference.COMPACT,
    )

    assert expanded == CubeStackPresentationFrame(
        CUBE_STACK_EXPANDED_WIDTH,
        CUBE_ITEM_EXPANDED_WIDTH,
        0.0,
        0.0,
        0.0,
    )
    assert compact == CubeStackPresentationFrame(
        CUBE_STACK_COMPACT_WIDTH,
        CUBE_ITEM_COMPACT_WIDTH,
        1.0,
        1.0,
        0.0,
    )
    assert unavailable == CubeStackPresentationFrame(
        0,
        CUBE_ITEM_COMPACT_WIDTH,
        1.0,
        1.0,
        1.0,
    )


def test_frame_interpolation_uses_fixed_start_and_clamped_progress() -> None:
    """Frame interpolation should be reversible and free from accumulated deltas."""

    start = CubeStackPresentationFrame(240, 212, 0.0, 0.0, 0.0)
    target = CubeStackPresentationFrame(0, 44, 1.0, 1.0, 1.0)

    assert interpolate_cube_stack_frame(start, target, -1.0) == start
    assert interpolate_cube_stack_frame(start, target, 0.5) == (
        CubeStackPresentationFrame(120, 128, 0.5, 0.5, 0.5)
    )
    assert interpolate_cube_stack_frame(start, target, 2.0) == target
