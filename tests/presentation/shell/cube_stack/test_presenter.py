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

"""Contract tests for unified cube-stack presentation application."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.cube_stack_presenter import (
    CubeStackProtocol,
    CubeTabItemProtocol,
    CubeStackPresenter,
    CubeTabIconResolver,
)


class _TabItem:
    """Mutable cube-stack tab item double."""

    def __init__(self, route_key: str) -> None:
        """Store the initial route key."""

        self._route_key = route_key

    def routeKey(self) -> str:
        """Return the current route key."""

        return self._route_key

    def setRouteKey(self, key: str) -> None:
        """Replace the current route key."""

        self._route_key = key


class _CubeStack:
    """Cube-stack double that records complete tab presentation."""

    def __init__(self) -> None:
        """Initialize tab, map, and selection records."""

        self.items: list[_TabItem] = []
        self.itemMap: dict[str, CubeTabItemProtocol] = {}
        self.tabs: list[dict[str, object]] = []
        self.presentations: dict[int, dict[str, str]] = {}
        self.icons: dict[int, object] = {}
        self.bypassed: dict[int, bool] = {}
        self.current_index = -1

    def clear(self) -> None:
        """Clear all recorded tab state."""

        self.items.clear()
        self.itemMap.clear()
        self.tabs.clear()
        self.presentations.clear()
        self.icons.clear()
        self.bypassed.clear()
        self.current_index = -1

    def count(self) -> int:
        """Return the current tab count."""

        return len(self.items)

    def insertTab(
        self,
        index: int,
        *,
        routeKey: str,
        text: str,
        icon: object | None = None,
    ) -> object:
        """Insert one tab and record initial metadata."""

        item = _TabItem(routeKey)
        self.items.insert(index, item)
        self.itemMap[routeKey] = item
        self.tabs.insert(index, {"routeKey": routeKey, "text": text, "icon": icon})
        return item

    def setCurrentIndex(self, index: int) -> None:
        """Record selected tab index."""

        self.current_index = index

    def setTabIcon(self, index: int, icon: object) -> None:
        """Record mandatory icon application."""

        self.icons[index] = icon
        self.tabs[index]["icon"] = icon

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None:
        """Record rich tab presentation."""

        self.presentations[index] = {
            "primary_text": primary_text,
            "secondary_text": secondary_text,
            "tooltip_text": tooltip_text,
        }
        self.tabs[index]["text"] = primary_text

    def setTabBypassed(self, index: int, bypassed: bool) -> None:
        """Record cube-level bypass presentation."""

        self.bypassed[index] = bypassed

    def tabItem(self, index: int) -> _TabItem:
        """Return one tab item."""

        return self.items[index]


def test_rebuild_stack_applies_complete_tab_presentation() -> None:
    """Stack rebuild should apply route key, labels, tooltip, icon, and selection."""

    icon_calls: list[dict[str, object]] = []

    def _resolve_icon(**kwargs: object) -> object:
        """Record one icon request and return a resolved token."""

        icon_calls.append(kwargs)
        return "resolved-icon"

    presenter = CubeStackPresenter(
        icon_resolver=CubeTabIconResolver(
            cube_icon_factory=SimpleNamespace(icon_for_cube=_resolve_icon)
        )
    )
    stack = _CubeStack()
    cube_state = CubeState(
        cube_id="Org/Base-Cubes/Base.cube",
        version="1.0.0",
        alias="Alias",
        original_cube={},
        buffer={},
        display_name="Base Display",
        ui={
            "cube_icon": "icon-descriptor",
            "catalog_revision": "rev-1",
            "content_hash": "hash-1",
        },
        bypassed=True,
    )

    result = presenter.rebuild_stack(
        cast(CubeStackProtocol, stack),
        workflow_id="wf-a",
        workflow=WorkflowState(cubes={"Alias": cube_state}, stack_order=["Alias"]),
        active_cube_alias="Alias",
    )

    assert result.inserted_count == 1
    assert result.selected_index == 0
    assert stack.tabs == [
        {"routeKey": "Alias", "text": "Alias", "icon": "resolved-icon"}
    ]
    assert stack.presentations[0]["secondary_text"] == "v1.0.0 · base-cubes"
    assert stack.bypassed[0] is True
    assert "Base Display" in stack.presentations[0]["tooltip_text"]
    assert stack.itemMap["Alias"].routeKey() == "Alias"
    assert stack.current_index == 0
    assert icon_calls == [
        {
            "cube_id": "Org/Base-Cubes/Base.cube",
            "display_name": "Base Display",
            "icon": "icon-descriptor",
            "catalog_revision": "rev-1",
            "cube_content_hash": "hash-1",
        }
    ]


def test_append_cube_adds_complete_selected_card_at_end() -> None:
    """Appending should reuse complete presentation and select the final card."""

    presenter = CubeStackPresenter(
        icon_resolver=CubeTabIconResolver(cube_icon_factory=None)
    )
    stack = _CubeStack()
    stack.insertTab(0, routeKey="Existing", text="Existing")
    duplicate = CubeState(
        cube_id="Org/Base-Cubes/Base.cube",
        version="1.2.0",
        alias="Existing 2",
        original_cube={},
        buffer={},
        bypassed=True,
    )

    presenter.append_cube(
        cast(CubeStackProtocol, stack),
        workflow_id="wf-a",
        cube_alias="Existing 2",
        cube_state=duplicate,
    )

    assert [tab["routeKey"] for tab in stack.tabs] == ["Existing", "Existing 2"]
    assert stack.presentations[1]["primary_text"] == "Existing 2"
    assert stack.presentations[1]["secondary_text"] == "v1.2.0 · base-cubes"
    assert stack.bypassed[1] is True
    assert stack.current_index == 1


def test_rebuild_stack_applies_fallback_icon_when_resolution_fails() -> None:
    """Icon resolution failure should still leave a final icon on the tab."""

    def _raise_icon_error(**_kwargs: object) -> object:
        """Raise an expected icon resolution failure."""

        raise RuntimeError("missing icon asset")

    presenter = CubeStackPresenter(
        icon_resolver=CubeTabIconResolver(
            cube_icon_factory=SimpleNamespace(icon_for_cube=_raise_icon_error)
        )
    )
    stack = _CubeStack()
    cube_state = CubeState(
        cube_id="Org/Base-Cubes/Base.cube",
        version="1.0.0",
        alias="Alias",
        original_cube={},
        buffer={},
        display_name="Base Display",
        ui={},
    )

    result = presenter.rebuild_stack(
        cast(CubeStackProtocol, stack),
        workflow_id="wf-a",
        workflow=WorkflowState(cubes={"Alias": cube_state}, stack_order=["Alias"]),
        active_cube_alias="Alias",
    )

    assert result.tab_results[0].used_fallback_icon is True
    assert stack.icons == {0: AppIcon.CUBE_20_FILLED}
    assert stack.tabs[0]["icon"] is AppIcon.CUBE_20_FILLED


def test_promote_placeholder_updates_route_key_and_complete_presentation() -> None:
    """Placeholder promotion should replace loading route state with cube state."""

    presenter = CubeStackPresenter(
        icon_resolver=CubeTabIconResolver(cube_icon_factory=None)
    )
    stack = _CubeStack()
    stack.insertTab(0, routeKey="loading:Alias", text="Loading...")
    cube_state = CubeState(
        cube_id="Org/Base-Cubes/Base.cube",
        version="1.0.0",
        alias="Alias",
        original_cube={},
        buffer={},
        display_name="Base Display",
        ui={},
    )

    result = presenter.promote_placeholder(
        cast(CubeStackProtocol, stack),
        0,
        workflow_id="wf-a",
        cube_alias="Alias",
        cube_state=cube_state,
    )

    assert result.applied_icon is True
    assert stack.tabItem(0).routeKey() == "Alias"
    assert "loading:Alias" not in stack.itemMap
    assert stack.itemMap["Alias"] is stack.tabItem(0)
    assert stack.tabs[0]["icon"] is AppIcon.CUBE_20_FILLED
    assert stack.current_index == 0
