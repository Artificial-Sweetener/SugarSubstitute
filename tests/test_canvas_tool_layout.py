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

"""Verify configurable canvas-toolbar grouping independently from Qt widgets."""

from __future__ import annotations

import pytest

from sugarsubstitute_shared.localization import app_text
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_canvas_tool_layout import (
    create_input_canvas_tool_layout,
)
from substitute.presentation.canvas.tools.layout import (
    CanvasToolGroupSlot,
    CanvasToolLayout,
    CanvasToolLayoutSnapshot,
)
from substitute.presentation.canvas.tools.layout_projection import (
    resolve_canvas_tool_slots,
)
from substitute.presentation.canvas.tools.layout_codec import CanvasToolLayoutCodec
from substitute.presentation.canvas.tools.model import (
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolPresentation,
)


def _presentation(
    tool_id: str,
    *,
    active: bool = False,
    enabled: bool = True,
) -> CanvasToolPresentation:
    """Build one inert presentation for layout resolution."""

    return CanvasToolPresentation(
        contribution=CanvasToolContribution(
            tool_id=tool_id,
            label=app_text(tool_id),
            icon=object(),
            kind=CanvasToolKind.MODE,
            section="test",
            order=0,
        ),
        enabled=enabled,
        active=active,
    )


def test_layout_rejects_duplicate_membership_and_invalid_representatives() -> None:
    """Durable grouping must reject ambiguous or unrecoverable identities."""

    with pytest.raises(ValueError, match="belong"):
        CanvasToolGroupSlot("shape", ("rectangle",), "ellipse")
    rectangle = CanvasToolGroupSlot("shape", ("rectangle",), "rectangle")
    duplicate = CanvasToolGroupSlot("duplicate", ("rectangle",), "rectangle")
    with pytest.raises(ValueError, match="more than once"):
        CanvasToolLayoutSnapshot((rectangle, duplicate))


def test_layout_resolves_active_then_remembered_then_first_available_member() -> None:
    """One group should present active state without losing durable preference."""

    layout = CanvasToolLayoutSnapshot(
        (
            CanvasToolGroupSlot(
                "shape",
                ("rectangle", "ellipse", "lasso"),
                "ellipse",
            ),
        )
    )

    remembered = resolve_canvas_tool_slots(
        (_presentation("rectangle"), _presentation("ellipse")),
        layout,
    )
    active = resolve_canvas_tool_slots(
        (
            _presentation("rectangle"),
            _presentation("ellipse"),
            _presentation("lasso", active=True),
        ),
        layout,
    )
    fallback = resolve_canvas_tool_slots((_presentation("rectangle"),), layout)

    assert remembered[0].tool_id == "ellipse"
    assert active[0].tool_id == "lasso"
    assert fallback[0].tool_id == "rectangle"


def test_layout_preserves_missing_members_and_appends_runtime_tools() -> None:
    """Provider churn must not rewrite durable groups or hide new contributions."""

    layout = CanvasToolLayout(
        CanvasToolLayoutSnapshot(
            (
                CanvasToolGroupSlot(
                    "shape",
                    ("rectangle", "missing"),
                    "missing",
                ),
            )
        )
    )

    projected = resolve_canvas_tool_slots(
        (_presentation("rectangle"), _presentation("workflow")),
        layout.snapshot(),
    )

    assert tuple(slot.tool_id for slot in projected) == ("rectangle", "workflow")
    assert layout.snapshot().slots[0].selected_tool_id == "missing"


def test_layout_mutations_publish_atomic_snapshots() -> None:
    """Customization commands should publish complete validated arrangements."""

    layout = CanvasToolLayout(
        CanvasToolLayoutSnapshot(
            (
                CanvasToolGroupSlot("shape", ("rectangle", "ellipse"), "rectangle"),
                CanvasToolGroupSlot("paint", ("brush",), "brush"),
            )
        )
    )
    changes: list[CanvasToolLayoutSnapshot] = []
    layout.subscribe(changes.append)

    assert layout.select_group_tool("shape", "ellipse")
    assert layout.move_slot("paint", 0)

    assert changes[0].slots[0].selected_tool_id == "ellipse"
    assert tuple(slot.slot_id for slot in changes[-1].slots) == ("paint", "shape")


def test_layout_supports_group_reassignment_visibility_and_round_trip() -> None:
    """Future customization should mutate and persist stable identities only."""

    layout = CanvasToolLayout(
        CanvasToolLayoutSnapshot(
            (
                CanvasToolGroupSlot("shape", ("rectangle", "ellipse"), "ellipse"),
                CanvasToolGroupSlot("paint", ("brush",), "brush"),
            )
        )
    )

    assert layout.move_tool("ellipse", "paint", 0)
    assert layout.set_tool_hidden("brush", True)
    snapshot = layout.snapshot()
    restored = CanvasToolLayoutCodec().decode(CanvasToolLayoutCodec().encode(snapshot))

    assert snapshot == restored
    assert snapshot.slots[0].tool_ids == ("rectangle",)
    assert snapshot.slots[0].selected_tool_id == "rectangle"
    assert snapshot.slots[1].tool_ids == ("ellipse", "brush")
    assert snapshot.hidden_tool_ids == frozenset({"brush"})


def test_layout_codec_rejects_unknown_schema_versions() -> None:
    """Persistence migrations must fail explicitly instead of guessing structure."""

    with pytest.raises(ValueError, match="unsupported"):
        CanvasToolLayoutCodec().decode({"version": 99, "slots": []})


def test_layout_codec_discards_legacy_visual_separators() -> None:
    """Older layouts must retain tools while adopting canonical even spacing."""

    codec = CanvasToolLayoutCodec()
    restored = codec.decode(
        {
            "version": 1,
            "slots": [
                {
                    "slot_id": "navigation",
                    "tool_ids": ["pan"],
                    "selected_tool_id": "pan",
                    "separated_before": True,
                }
            ],
        }
    )

    encoded_slots = codec.encode(restored)["slots"]
    assert isinstance(encoded_slots, list)
    encoded_slot = encoded_slots[0]
    assert isinstance(encoded_slot, dict)
    assert "separated_before" not in encoded_slot
    assert restored.slots[0].tool_ids == ("pan",)


def test_input_default_layout_groups_like_tools_without_hiding_extensibility() -> None:
    """Product defaults should group shapes while retaining stable singleton slots."""

    snapshot = create_input_canvas_tool_layout().snapshot()

    assert tuple(slot.slot_id for slot in snapshot.slots) == (
        "input.slot.navigation",
        "input.slot.move",
        "input.slot.brush",
        "input.slot.eraser",
        "input.slot.selection_shapes",
        "input.slot.smart_select",
        "input.slot.mask_shapes",
        "input.slot.smart_mask",
        "input.slot.transform",
    )
    assert snapshot.slots[4].tool_ids == (
        InputCanvasToolId.SELECT_RECTANGLE,
        InputCanvasToolId.SELECT_ELLIPSE,
        InputCanvasToolId.SELECT_LASSO,
    )
    assert snapshot.slots[6].tool_ids == (
        InputCanvasToolId.MASK_RECTANGLE,
        InputCanvasToolId.MASK_ELLIPSE,
        InputCanvasToolId.MASK_LASSO,
    )
