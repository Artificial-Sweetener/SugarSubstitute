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

"""Verify Output source-tab widget mutation outside the canvas widget."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_source_tabs_controller import (
    OutputCanvasSourceTabsController,
)


def test_rebuild_source_tabs_refreshes_preferred_width() -> None:
    """Source tab rebuilds should cache the full width used for resize decisions."""

    synced: list[None] = []
    tabbar = _Tabbar(width=222)
    harness = _controller(
        tabbar=tabbar,
        sources=(
            OutputCanvasSourceGroup("txt", "Text", {}),
            OutputCanvasSourceGroup("up", "Upscale", {}),
        ),
        syncs=synced,
    )

    harness.controller.rebuild_source_tabs(active_source_key="up")

    assert harness.preferred_widths == [0, 222]
    assert tabbar.current == "up"
    assert synced == [None]


def test_rebuild_source_tabs_skips_unchanged_tab_identity() -> None:
    """Source tab rebuild should avoid remove/add churn for unchanged sources."""

    synced: list[None] = []
    tabbar = _Tabbar(width=222)
    harness = _controller(
        tabbar=tabbar,
        sources=(
            OutputCanvasSourceGroup("txt", "Text", {}),
            OutputCanvasSourceGroup("up", "Upscale", {}),
        ),
        syncs=synced,
    )

    harness.controller.rebuild_source_tabs(active_source_key="up")
    harness.controller.rebuild_source_tabs(active_source_key="up")

    assert tabbar.removed == []
    assert tabbar.added == [("txt", "Text"), ("up", "Upscale")]
    assert tabbar.current == "up"
    assert synced == [None, None]


def test_rebuild_source_tabs_installs_tooltip_for_active_set_metadata() -> None:
    """Source tab tooltips should show representative resolution and cube timing."""

    installed: list[tuple[object, int]] = []
    tabbar = _Tabbar(width=222)
    source = OutputCanvasSourceGroup(
        "txt",
        "Text",
        {
            1: OutputCanvasImageItem(
                uuid4(),
                _image_meta(
                    "Text",
                    image_number=1,
                    width=512,
                    height=512,
                    duration_ms=1.0,
                ),
                1,
            ),
            2: OutputCanvasImageItem(
                uuid4(),
                _image_meta(
                    "Text",
                    image_number=2,
                    width=1024,
                    height=768,
                    duration_ms=3080.0,
                ),
                2,
            ),
        },
    )
    harness = _controller(
        tabbar=tabbar,
        sources=(source,),
        active_set_index=2,
        installed=installed,
    )

    harness.controller.rebuild_source_tabs(active_source_key="txt")

    assert tabbar.items["txt"].tooltip == "1024x768\n3.1s"
    assert installed == [(tabbar.items["txt"], 600)]
    assert str(harness.tooltip_filter_map["txt"]).startswith("filter:")


def test_rebuild_source_tabs_skips_tooltip_filter_without_metadata() -> None:
    """Source tab tooltips should remain unset when metadata has no display values."""

    installed: list[tuple[object, int]] = []
    tabbar = _Tabbar(width=222)
    source = OutputCanvasSourceGroup(
        "txt",
        "Text",
        {1: OutputCanvasImageItem(uuid4(), _image_meta("Text"), 1)},
    )
    harness = _controller(
        tabbar=tabbar,
        sources=(source,),
        installed=installed,
    )

    harness.controller.rebuild_source_tabs(active_source_key="txt")

    assert tabbar.items["txt"].tooltip == ""
    assert installed == []
    assert harness.tooltip_filter_map == {}


@dataclass(frozen=True, slots=True)
class _ControllerHarness:
    """Bundle source-tab controller state inspected by tests."""

    controller: OutputCanvasSourceTabsController
    preferred_widths: list[int]
    tooltip_filter_map: dict[str, object]


class _Signal:
    """Small signal double used by controller tests."""

    def __init__(self) -> None:
        """Initialize an empty slot list."""

        self._slots: list[object] = []

    def connect(self, slot: object) -> None:
        """Record one connected slot."""

        self._slots.append(slot)

    def disconnect(self, slot: object) -> None:
        """Disconnect one slot or mimic Qt's missing-slot RuntimeError."""

        if slot not in self._slots:
            raise RuntimeError("slot not connected")
        self._slots.remove(slot)


class _TabItem:
    """Record tab item tooltip state."""

    def __init__(self, label: str) -> None:
        """Store the label and initialize empty tooltip text."""

        self.label = label
        self.tooltip: str | None = None

    def setToolTip(self, text: str) -> None:  # noqa: N802
        """Record the assigned tooltip text."""

        self.tooltip = text


class _Tabbar:
    """Record source-tab mutations requested by the controller."""

    def __init__(self, *, width: int) -> None:
        """Initialize tabbar state with a deterministic size hint."""

        self.items: dict[str, _TabItem] = {}
        self.currentItemChanged = _Signal()
        self.current: str | None = None
        self.added: list[tuple[str, str]] = []
        self.removed: list[str] = []
        self._width = width

    def addItem(self, key: str, label: str) -> None:  # noqa: N802
        """Record and create one source-tab item."""

        self.added.append((key, label))
        self.items[key] = _TabItem(label)

    def removeWidget(self, key: str) -> None:  # noqa: N802
        """Record and remove one source-tab item."""

        self.removed.append(key)
        self.items.pop(key, None)

    def adjustSize(self) -> None:  # noqa: N802
        """No-op size settle hook for controller tests."""

    def sizeHint(self) -> _SizeHint:  # noqa: N802
        """Return an object exposing a deterministic width."""

        return _SizeHint(self._width)

    def setCurrentItem(self, key: str) -> None:  # noqa: N802
        """Record the selected source-tab key."""

        self.current = key


@dataclass(frozen=True, slots=True)
class _SizeHint:
    """Expose deterministic tabbar size-hint width."""

    value: int

    def width(self) -> int:
        """Return the configured width."""

        return self.value


def _controller(
    *,
    tabbar: _Tabbar,
    sources: tuple[OutputCanvasSourceGroup, ...],
    active_set_index: int = 1,
    syncs: list[None] | None = None,
    installed: list[tuple[object, int]] | None = None,
) -> _ControllerHarness:
    """Return a source-tab controller with deterministic collaborators."""

    signature: tuple[tuple[str, str], ...] | None = None
    preferred_widths: list[int] = []
    tooltip_filter_map: dict[str, object] = {}
    active_syncs = syncs if syncs is not None else []
    active_installed = installed if installed is not None else []

    def set_signature(value: tuple[tuple[str, str], ...]) -> None:
        nonlocal signature
        signature = value

    controller = OutputCanvasSourceTabsController(
        visible_sources=lambda: sources,
        cached_signature=lambda: signature,
        set_cached_signature=set_signature,
        set_preferred_width=preferred_widths.append,
        tabbar=lambda: tabbar,
        on_tab_changed=lambda _key: None,
        active_set_index=lambda: active_set_index,
        tooltip_filters=lambda: tooltip_filter_map,
        measure_preferred_width=lambda: tabbar.sizeHint().width(),
        sync_source_selector=lambda: active_syncs.append(None),
        install_tooltip_filter=lambda tab_item, _parent, delay: _install_filter(
            active_installed,
            tab_item,
            delay,
        ),
    )
    return _ControllerHarness(
        controller=controller,
        preferred_widths=preferred_widths,
        tooltip_filter_map=tooltip_filter_map,
    )


def _install_filter(
    installed: list[tuple[object, int]],
    tab_item: object,
    delay: int,
) -> object:
    """Record tooltip filter installation and return an opaque handle."""

    installed.append((tab_item, delay))
    return f"filter:{id(tab_item)}"


def _image_meta(
    label: str,
    *,
    image_number: int = 1,
    width: int | None = None,
    height: int | None = None,
    duration_ms: float | None = None,
) -> ImageMeta:
    """Return typed image metadata for source-tab tooltip tests."""

    return ImageMeta(
        workflow_name="wf",
        cube_name=label,
        image_number=image_number,
        suffix="",
        path=f"E:/{label}_{image_number}.png",
        source_key=label.lower(),
        width=width,
        height=height,
        cube_execution_duration_ms=duration_ms,
    )
