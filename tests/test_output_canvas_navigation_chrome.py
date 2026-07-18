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

"""Verify Output canvas floating navigation chrome seams."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)

from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)


def _refresh_tabbar_container(fake: Any) -> None:
    """Call the navigation chrome adapter with composed collaborators."""

    _install_navigation_controller(fake)
    update_output_tabbar_container(
        fake,
        single_shot=lambda _ms, callback: callback(),
    )


def _schedule_tabbar_container_update(
    fake: Any,
    scheduled_callbacks: list[Any],
) -> None:
    """Call the navigation chrome adapter and capture deferred geometry callbacks."""

    _install_navigation_controller(fake)
    update_output_tabbar_container(
        fake,
        single_shot=lambda _ms, callback: scheduled_callbacks.append(callback),
    )


def _install_navigation_controller(fake: Any) -> None:
    """Install the navigation collaborator required by lightweight hosts."""

    setattr(
        fake,
        "_navigation_controller",
        OutputCanvasNavigationController(
            canvas_width=lambda: (
                int(fake.width()) if callable(getattr(fake, "width", None)) else None
            ),
            tabbar=lambda: fake.tabbar,
            cached_source_tabbar_width=lambda: int(
                getattr(fake, "_source_tabbar_preferred_width", 0) or 0
            ),
            set_cached_source_tabbar_width=lambda width: setattr(
                fake,
                "_source_tabbar_preferred_width",
                width,
            ),
        ),
    )


class _Widget:
    """Small widget double for Output navigation chrome geometry tests."""

    def __init__(
        self,
        width: int = 0,
        height: int = 28,
        *,
        size_hint_width: int = 0,
    ) -> None:
        """Store fixed geometry values exposed through Qt-like methods."""

        self._width = width
        self._height = height
        self._size_hint_width = size_hint_width
        self.hidden = 0
        self.shown = 0
        self.visible: bool | None = None
        self.geometries: list[tuple[int, int, int, int]] = []
        self.items: dict[str, object] = {}

    def hide(self) -> None:
        """Record a hide call."""

        self.hidden += 1
        self.visible = False

    def show(self) -> None:
        """Record a show call."""

        self.shown += 1
        self.visible = True

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Record a Qt-style visibility mutation."""

        self.visible = visible
        if visible:
            self.shown += 1
            return
        self.hidden += 1

    def width(self) -> int:
        """Return the configured widget width."""

        return self._width

    def height(self) -> int:
        """Return the configured widget height."""

        return self._height

    def sizeHint(self) -> object:  # noqa: N802
        """Return a Qt-like size hint object."""

        return SimpleNamespace(
            width=lambda: self._size_hint_width,
            height=lambda: self._height,
        )

    def setGeometry(self, x: int, y: int, width: int, height: int) -> None:  # noqa: N802
        """Record a Qt-style geometry mutation."""

        self.geometries.append((x, y, width, height))

    def raise_(self) -> None:
        """Accept Qt-style z-order calls."""

        return None

    def lower(self) -> None:
        """Accept Qt-style z-order calls."""

        return None


def _scene_chrome_host(*, batch_count: int) -> SimpleNamespace:
    """Return a lightweight scene-overview host with uniform batch counts."""

    scenes = tuple(
        OutputCanvasSceneGroup(
            scene_run_id="run",
            scene_key=f"scene{scene_index}",
            title=f"Scene {scene_index}",
            order=scene_index,
            sources=(
                OutputCanvasSourceGroup(
                    source_key="text",
                    label="Text",
                    images_by_set={
                        set_index: cast(Any, object())
                        for set_index in range(1, batch_count + 1)
                    },
                ),
            ),
        )
        for scene_index in range(1, 4)
    )
    tabbar = _Widget(size_hint_width=80)
    tabbar.items = {"text": object()}
    return SimpleNamespace(
        tabbar=tabbar,
        scene_selector_button=_Widget(width=58),
        set_selector_button=_Widget(width=34),
        source_selector_button=_Widget(width=58),
        tabbar_container=_Widget(),
        tabbar_bg=_Widget(),
        comparison_nav_container=_Widget(),
        _output_projection=OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
            scene_groups=scenes,
            active_scene_overview=True,
            scene_count=3,
        ),
        scene_count=3,
        active_scene_key=None,
        active_scene_overview=True,
        set_count=0,
        active_set_index=1,
        active_source_key=None,
        source_groups={},
        preview_ids_by_source_key={},
        height=lambda: 400,
        width=lambda: 600,
    )


def test_refresh_tabbar_container_visibility_and_geometry() -> None:
    """Tabbar container should hide for <2 items and place 2+ item chrome."""

    tabbar = _Widget(size_hint_width=120)
    tabbar.items = {"one": object()}
    selector = _Widget(width=34)
    container = _Widget()
    background = _Widget()
    fake = SimpleNamespace(
        tabbar=tabbar,
        set_selector_button=selector,
        tabbar_container=container,
        tabbar_bg=background,
        set_count=1,
        active_source_key=None,
        source_groups={},
        preview_ids_by_source_key={},
        height=lambda: 400,
    )

    _refresh_tabbar_container(fake)
    assert tabbar.hidden == 1
    assert container.hidden == 1

    tabbar.items = {"one": object(), "two": object()}
    _refresh_tabbar_container(fake)

    assert tabbar.shown == 1
    assert container.shown == 1
    assert container.geometries[-1] == (8, 356, 128, 36)
    assert background.geometries[-1] == (0, 0, 128, 36)
    assert tabbar.geometries[-1] == (4, 4, 120, 28)

    tabbar.items = {"one": object()}
    fake.set_count = 4
    _refresh_tabbar_container(fake)

    assert selector.shown == 1
    assert container.shown == 2


def test_scene_chrome_requires_real_batch_alternatives() -> None:
    """Scene and batch controls should hide when every scene has one result set."""

    batchless = _scene_chrome_host(batch_count=1)

    _refresh_tabbar_container(batchless)

    assert batchless.scene_selector_button.visible is False
    assert batchless.set_selector_button.visible is False
    assert batchless.tabbar_container.visible is False

    batched = _scene_chrome_host(batch_count=2)

    _refresh_tabbar_container(batched)

    assert batched.scene_selector_button.visible is True
    assert batched.set_selector_button.visible is False
    assert batched.tabbar_container.visible is True


def test_one_tile_grid_route_hides_batch_selector() -> None:
    """Internal All Batches state should not create a useless one-item control."""

    tabbar = _Widget(size_hint_width=80)
    tabbar.items = {"text": object()}
    fake = SimpleNamespace(
        tabbar=tabbar,
        set_selector_button=_Widget(width=34),
        source_selector_button=_Widget(width=58),
        tabbar_container=_Widget(),
        tabbar_bg=_Widget(),
        comparison_nav_container=_Widget(),
        scene_count=1,
        active_scene_overview=False,
        set_count=1,
        active_set_index=0,
        active_source_key="text",
        source_groups={},
        preview_ids_by_source_key={},
        height=lambda: 400,
        width=lambda: 600,
    )

    _refresh_tabbar_container(fake)

    assert fake.set_selector_button.visible is False
    assert fake.tabbar_container.visible is False


def test_source_tabs_collapse_and_expand_on_width() -> None:
    """Source tabs should switch between tabbar and picker button on resize."""

    canvas_width = 600
    tabbar = _Widget(size_hint_width=300)
    tabbar.items = {"one": object(), "two": object()}
    source_selector = _Widget(width=72)
    fake = SimpleNamespace(
        tabbar=tabbar,
        set_selector_button=_Widget(width=34),
        source_selector_button=source_selector,
        tabbar_container=_Widget(),
        tabbar_bg=_Widget(),
        set_count=1,
        active_source_key="one",
        active_scene_overview=False,
        source_groups={},
        preview_ids_by_source_key={},
        height=lambda: 400,
        width=lambda: canvas_width,
    )

    _refresh_tabbar_container(fake)

    assert fake._source_tabs_collapsed is False
    assert tabbar.visible is True
    assert source_selector.visible is False

    canvas_width = 250
    _refresh_tabbar_container(fake)

    assert fake._source_tabs_collapsed is True
    assert tabbar.visible is False
    assert source_selector.visible is True

    canvas_width = 600
    _refresh_tabbar_container(fake)

    assert fake._source_tabs_collapsed is False
    assert tabbar.visible is True
    assert source_selector.visible is False


def test_source_collapse_decision_uses_full_tab_width() -> None:
    """Collapsed picker width must not make source tabs re-expand early."""

    canvas_width = 520
    tabbar = _Widget(size_hint_width=500)
    tabbar.items = {"one": object(), "two": object()}
    source_selector = _Widget(width=58)
    fake = SimpleNamespace(
        tabbar=tabbar,
        set_selector_button=_Widget(width=34),
        source_selector_button=source_selector,
        tabbar_container=_Widget(),
        tabbar_bg=_Widget(),
        set_count=1,
        active_source_key="one",
        active_scene_overview=False,
        source_groups={},
        preview_ids_by_source_key={},
        height=lambda: 400,
        width=lambda: canvas_width,
    )

    _refresh_tabbar_container(fake)

    assert fake._source_tabs_collapsed is True
    assert source_selector.visible is True

    canvas_width = 532
    _refresh_tabbar_container(fake)

    assert fake._source_tabs_collapsed is False
    assert tabbar.visible is True


def test_deferred_tabbar_geometry_remeasures_settled_width() -> None:
    """Deferred tabbar geometry should not use a stale zero rebuild width."""

    scheduled_callbacks: list[Any] = []
    settled_tabbar_width = 0
    tabbar = _Widget()
    tabbar.items = {"one": object(), "two": object()}
    source_selector = _Widget(width=72)
    fake = SimpleNamespace(
        tabbar=tabbar,
        set_selector_button=_Widget(width=34),
        source_selector_button=source_selector,
        tabbar_container=_Widget(),
        tabbar_bg=_Widget(),
        set_count=1,
        active_source_key="one",
        active_scene_overview=False,
        source_groups={},
        preview_ids_by_source_key={},
        _source_tabbar_preferred_width=0,
        height=lambda: 400,
        width=lambda: 600,
    )

    _schedule_tabbar_container_update(fake, scheduled_callbacks)

    assert len(scheduled_callbacks) == 1
    assert tabbar.visible is True

    settled_tabbar_width = 312
    tabbar._size_hint_width = settled_tabbar_width
    scheduled_callbacks.pop()()

    assert fake._source_tabs_collapsed is False
    assert tabbar.visible is True
    assert source_selector.visible is False
    assert fake.tabbar_container.geometries[-1][2] == 320
    assert tabbar.geometries[-1][2] == 312
