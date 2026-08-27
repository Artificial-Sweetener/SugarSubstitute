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

"""Provide typed Output navigation controller test doubles."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)


@dataclass(slots=True)
class SignalSpy:
    """Small signal double that records emitted payloads."""

    calls: list[tuple[object, ...]] = field(default_factory=list)

    def emit(self, *args: object) -> None:
        """Record emitted signal arguments."""

        self.calls.append(args)


class SelectorButtonSpy:
    """Record selector button writes from navigation adapters."""

    def __init__(self) -> None:
        """Create an unset selector button."""

        self.text = ""
        self.visible = False
        self.fixed_width = 0
        self.tooltip = ""

    def setText(self, text: str) -> None:
        """Record selector text."""

        self.text = text

    def setVisible(self, visible: bool) -> None:
        """Record selector visibility."""

        self.visible = visible

    def setFixedWidth(self, width: int) -> None:
        """Record selector width."""

        self.fixed_width = width

    def setToolTip(self, tooltip: str) -> None:
        """Record selector tooltip."""

        self.tooltip = tooltip

    def fontMetrics(self) -> object:  # noqa: N802
        """Return deterministic text metrics."""

        return SimpleNamespace(horizontalAdvance=lambda text: len(text) * 8)


class ContainerSpy:
    """Record navigation container visibility mutations."""

    def __init__(self) -> None:
        """Create a visible container spy."""

        self.hidden = False

    def hide(self) -> None:
        """Record that the container was hidden."""

        self.hidden = True


@dataclass(slots=True)
class WidgetStub:
    """Small widget double exposing width and sizeHint."""

    width_value: int = 0
    size_hint_width: int = 0

    def ensurePolished(self) -> None:  # noqa: N802
        """No-op Qt polish hook."""

    def adjustSize(self) -> None:  # noqa: N802
        """No-op Qt size adjustment hook."""

    def sizeHint(self) -> object:  # noqa: N802
        """Return a minimal Qt-like size hint."""

        return SimpleNamespace(width=lambda: self.size_hint_width)

    def width(self) -> int:
        """Return configured width."""

        return self.width_value


@dataclass(slots=True)
class LayoutSpy:
    """Small layout double exposing spacing and margins."""

    spacing_value: int
    left: int
    right: int
    invalidated: bool = False
    activated: bool = False

    def invalidate(self) -> None:
        """Record invalidation."""

        self.invalidated = True

    def activate(self) -> None:
        """Record activation."""

        self.activated = True

    def spacing(self) -> int:
        """Return configured spacing."""

        return self.spacing_value

    def contentsMargins(self) -> object:  # noqa: N802
        """Return minimal Qt-like margins."""

        return SimpleNamespace(
            left=lambda: self.left,
            right=lambda: self.right,
        )


@dataclass(slots=True)
class PlacedWidgetSpy:
    """Small widget double that records placement and z-order calls."""

    geometries: list[tuple[int, int, int, int]] = field(default_factory=list)
    visible: bool | None = None
    hidden: bool = False
    raised: bool = False
    lowered: bool = False
    shown: bool = False

    def setGeometry(self, x: int, y: int, width: int, height: int) -> None:  # noqa: N802
        """Record assigned geometry."""

        self.geometries.append((x, y, width, height))

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Record assigned visibility."""

        self.visible = visible

    def hide(self) -> None:
        """Record hide request."""

        self.hidden = True
        self.visible = False

    def raise_(self) -> None:
        """Record raise request."""

        self.raised = True

    def lower(self) -> None:
        """Record lower request."""

        self.lowered = True

    def show(self) -> None:
        """Record show request."""

        self.shown = True


def build_controller(
    *,
    canvas_width: int | None = 400,
    tabbar: object | None = None,
    cached_width: int = 0,
    cached_updates: list[int] | None = None,
) -> OutputCanvasNavigationController:
    """Return a navigation controller with deterministic collaborators."""

    updates = cached_updates if cached_updates is not None else []
    return OutputCanvasNavigationController(
        canvas_width=lambda: canvas_width,
        tabbar=lambda: tabbar or WidgetStub(width_value=120, size_hint_width=0),
        cached_source_tabbar_width=lambda: cached_width,
        set_cached_source_tabbar_width=updates.append,
    )


def build_output_item(*, set_index: int) -> OutputCanvasImageItem:
    """Return a typed output item for navigation policy tests."""

    return OutputCanvasImageItem(
        uuid4(),
        ImageMeta("Workflow", "Cube", set_index - 1, "", "E:/outputs/image.png"),
        set_index,
    )


def build_source(
    source_key: str,
    *,
    set_indexes: tuple[int, ...],
) -> OutputCanvasSourceGroup:
    """Return a source group with deterministic image items."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=source_key,
        images_by_set={
            index: build_output_item(set_index=index) for index in set_indexes
        },
    )


def build_scene(
    scene_key: str,
    *,
    sources: tuple[OutputCanvasSourceGroup, ...],
    representative_source_key: str | None = None,
) -> OutputCanvasSceneGroup:
    """Return a scene group with deterministic navigation metadata."""

    return OutputCanvasSceneGroup(
        scene_run_id=f"{scene_key}-run",
        scene_key=scene_key,
        title=scene_key,
        order=0,
        sources=sources,
        representative_source_key=representative_source_key,
    )
