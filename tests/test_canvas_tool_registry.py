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

"""Verify runtime canvas-tool registration and contextual palette projection."""

from __future__ import annotations

import pytest

from sugarsubstitute_shared.localization import app_text
from substitute.presentation.canvas.tools.model import (
    CanvasToolContext,
    CanvasToolContribution,
    CanvasToolKind,
)
from substitute.presentation.canvas.tools.palette import CanvasToolPalette
from substitute.presentation.canvas.tools.registry import CanvasToolRegistry


def _tool(
    tool_id: str,
    *,
    order: int = 0,
    section: str = "main",
    contexts: frozenset[str] = frozenset({"canvas"}),
    capabilities: frozenset[str] = frozenset(),
    kind: CanvasToolKind = CanvasToolKind.MODE,
) -> CanvasToolContribution:
    """Return one inert contribution for registry tests."""

    return CanvasToolContribution(
        tool_id=tool_id,
        label=app_text(tool_id),
        icon=object(),
        kind=kind,
        section=section,
        order=order,
        required_context_tags=contexts,
        required_capabilities=capabilities,
    )


def test_registry_supports_runtime_add_remove_and_deterministic_order() -> None:
    """Runtime contributions should project in stable section and tool order."""

    registry = CanvasToolRegistry()
    changes: list[tuple[str, ...]] = []
    subscription = registry.subscribe(
        lambda tools: changes.append(tuple(tool.tool_id for tool in tools))
    )

    registry.register(_tool("brush", order=40, section="paint"))
    registry.register(_tool("move", order=10, section="direct"))
    registry.register(_tool("lasso", order=30, section="select"))
    registry.register(_tool("rectangle", order=20, section="select"))

    assert tuple(tool.tool_id for tool in registry.snapshot()) == (
        "move",
        "rectangle",
        "lasso",
        "brush",
    )
    assert registry.unregister("rectangle") is True
    assert registry.unregister("missing") is False
    assert tuple(tool.tool_id for tool in registry.snapshot()) == (
        "move",
        "lasso",
        "brush",
    )
    assert changes[-1] == ("move", "lasso", "brush")

    subscription.close()
    registry.register(_tool("pan", order=100, section="navigation"))
    assert changes[-1] == ("move", "lasso", "brush")


def test_registry_rejects_ambiguous_or_invalid_contributions() -> None:
    """Tool identities and placement metadata should fail closed."""

    registry = CanvasToolRegistry()
    registry.register(_tool("move"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(_tool("move"))
    with pytest.raises(ValueError, match="tool_id"):
        registry.register(_tool("  "))
    with pytest.raises(ValueError, match="section"):
        registry.register(_tool("bad-section", section=""))


def test_palette_filters_context_and_derives_enabled_state() -> None:
    """Visibility and enablement should derive from separate context concerns."""

    registry = CanvasToolRegistry()
    registry.register(_tool("pan", order=10, capabilities=frozenset({"image"})))
    registry.register(
        _tool(
            "brush",
            order=20,
            contexts=frozenset({"canvas", "mask-authoring"}),
            capabilities=frozenset({"active-mask"}),
        )
    )
    registry.register(
        _tool(
            "workflow-action",
            order=30,
            contexts=frozenset({"canvas", "workflow-tools"}),
            capabilities=frozenset({"image", "backend"}),
            kind=CanvasToolKind.ACTION,
        )
    )
    palette = CanvasToolPalette(registry)

    palette.set_context(
        CanvasToolContext(
            tags=frozenset({"canvas", "mask-authoring"}),
            capabilities=frozenset({"image"}),
        )
    )

    assert tuple(item.tool_id for item in palette.snapshot()) == ("pan", "brush")
    pan = palette.presentation_for("pan")
    brush = palette.presentation_for("brush")
    assert pan is not None and pan.enabled is True
    assert brush is not None and brush.enabled is False
    assert palette.presentation_for("workflow-action") is None

    palette.set_context(
        CanvasToolContext(
            tags=frozenset({"canvas", "mask-authoring", "workflow-tools"}),
            capabilities=frozenset({"image", "active-mask", "backend"}),
        )
    )

    brush = palette.presentation_for("brush")
    workflow_action = palette.presentation_for("workflow-action")
    assert brush is not None and brush.enabled is True
    assert workflow_action is not None and workflow_action.enabled is True


def test_palette_active_state_cannot_point_at_unavailable_or_removed_tool() -> None:
    """Active presentation must never retain a disabled, hidden, or stale tool."""

    registry = CanvasToolRegistry()
    registry.register(_tool("pan", capabilities=frozenset({"image"})))
    registry.register(_tool("brush", capabilities=frozenset({"active-mask"})))
    palette = CanvasToolPalette(registry)
    palette.set_context(
        CanvasToolContext(
            tags=frozenset({"canvas"}),
            capabilities=frozenset({"image", "active-mask"}),
        )
    )

    assert palette.set_active_tool("brush") is True
    brush = palette.presentation_for("brush")
    assert brush is not None and brush.active is True

    palette.set_context(
        CanvasToolContext(
            tags=frozenset({"canvas"}),
            capabilities=frozenset({"image"}),
        )
    )
    assert all(not item.active for item in palette.snapshot())
    assert palette.active_tool_id is None

    assert palette.set_active_tool("missing") is False
    assert palette.set_active_tool("pan") is True
    assert registry.unregister("pan") is True
    assert palette.active_tool_id is None


def test_registry_notification_tolerates_reentrant_runtime_removal() -> None:
    """A subscriber may remove a contribution without corrupting notification order."""

    registry = CanvasToolRegistry()
    observed: list[tuple[str, ...]] = []

    def remove_transient(tools: tuple[CanvasToolContribution, ...]) -> None:
        """Remove one transient tool on its first observable registration."""

        ids = tuple(tool.tool_id for tool in tools)
        observed.append(ids)
        if "transient" in ids:
            registry.unregister("transient")

    registry.subscribe(remove_transient)
    registry.register(_tool("stable"))
    registry.register(_tool("transient"))

    assert observed == [
        ("stable",),
        ("stable", "transient"),
        ("stable",),
    ]
    assert tuple(tool.tool_id for tool in registry.snapshot()) == ("stable",)
