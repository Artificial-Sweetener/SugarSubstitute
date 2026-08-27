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

"""Cube stack selection and indicator contracts."""

from __future__ import annotations

from typing import Any

from types import SimpleNamespace

from tests.presentation.workflows.tab_stack_support import (
    _SlideAnimation,
    _TabItem,
    _attach_cube_stack_selection_methods,
    _import_stack_panel_module,
)


def test_cube_stack_set_current_index_ignores_invalid_index() -> None:
    """setCurrentIndex should no-op for invalid index."""
    mod = _import_stack_panel_module()
    item = _TabItem("cube")
    fake: Any = SimpleNamespace(
        items=[item],
        _currentIndex=0,
        slideAni=_SlideAnimation(),
        currentIndex=lambda: fake._currentIndex,
        currentTab=lambda: item,
        setIndicatorY=lambda _value: None,
    )
    _attach_cube_stack_selection_methods(mod, fake)

    mod.CubeStack.setCurrentIndex(fake, 5)

    assert fake._currentIndex == 0
    assert fake.slideAni.started == 0


def test_cube_stack_set_current_index_animates_indicator_and_selection() -> None:
    """Valid setCurrentIndex updates selected tab and indicator animation target."""
    mod = _import_stack_panel_module()
    item0 = _TabItem("cube0")
    item1 = _TabItem("cube1")
    slide = _SlideAnimation()
    fake: Any = SimpleNamespace(
        items=[item0, item1],
        _currentIndex=0,
        slideAni=slide,
        currentIndex=lambda: fake._currentIndex,
        currentTab=lambda: fake.items[fake._currentIndex],
        setIndicatorY=lambda _value: None,
    )
    _attach_cube_stack_selection_methods(mod, fake)

    mod.CubeStack.setCurrentIndex(fake, 1)

    assert item0.selected is False
    assert item1.selected is True
    assert fake._currentIndex == 1
    assert slide.end_value == item1.y() + item1.height() // 2 - 8
    assert slide.duration == 220
    assert slide.started == 1


def test_cube_stack_reselects_current_index_to_realign_indicator() -> None:
    """Selecting the current tab again should repair stale indicator geometry."""

    mod = _import_stack_panel_module()
    item = _TabItem("cube")
    item._y = 20
    indicator_values: list[int] = []
    fake: Any = SimpleNamespace(
        items=[item],
        _currentIndex=0,
        slideAni=_SlideAnimation(),
        currentIndex=lambda: fake._currentIndex,
        currentTab=lambda: fake.items[fake._currentIndex],
        setIndicatorY=lambda value: indicator_values.append(value),
    )
    _attach_cube_stack_selection_methods(mod, fake)

    mod.CubeStack.realign_indicator(fake, animated=False)
    item._y = 84
    mod.CubeStack.setCurrentIndex(fake, 0)

    assert item.selected is True
    assert fake.slideAni.end_value == item.y() + item.height() // 2 - 8
    assert fake.slideAni.started == 1


def test_cube_stack_select_cube_uses_route_key_for_selection() -> None:
    """Route-key selection should resolve the current index from itemMap."""

    mod = _import_stack_panel_module()
    item0 = _TabItem("cube-a")
    item1 = _TabItem("cube-b")
    slide = _SlideAnimation()
    fake: Any = SimpleNamespace(
        items=[item0, item1],
        itemMap={"cube-a": item0, "cube-b": item1},
        _currentIndex=0,
        slideAni=slide,
        currentIndex=lambda: fake._currentIndex,
        currentTab=lambda: fake.items[fake._currentIndex],
        setIndicatorY=lambda _value: None,
    )
    _attach_cube_stack_selection_methods(mod, fake)

    mod.CubeStack.select_cube(fake, "cube-b", animated=True)

    assert item0.selected is False
    assert item1.selected is True
    assert fake._currentIndex == 1
    assert slide.end_value == item1.y() + item1.height() // 2 - 8


def test_cube_stack_indicator_realign_is_coalesced_on_owned_timer() -> None:
    """Tab layout mutations should schedule one owned deferred realignment."""

    mod = _import_stack_panel_module()
    starts: list[int] = []
    fake: Any = SimpleNamespace(
        _indicator_realign_pending=False,
        _indicator_realign_timer=SimpleNamespace(
            start=lambda interval: starts.append(interval)
        ),
    )

    mod.CubeStack._schedule_indicator_realign(fake)
    mod.CubeStack._schedule_indicator_realign(fake)

    assert starts == [0]
    assert fake._indicator_realign_pending is True
