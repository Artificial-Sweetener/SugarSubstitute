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

"""Test full projection loading through the EditorPanel façade."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch


class _LayoutItem:
    """Expose one widget from the panel layout."""

    def __init__(self, widget: object) -> None:
        """Store the layout widget."""

        self._widget = widget

    def widget(self) -> object:
        """Return the contained widget."""

        return self._widget

    def spacerItem(self) -> None:  # noqa: N802
        """Report that this item is not a spacer."""

        return None


class _Layout:
    """Record cube widgets and spacings added during full projection."""

    def __init__(self, widgets: list[object]) -> None:
        """Initialize removable source widgets."""

        self._items = [_LayoutItem(widget) for widget in widgets]
        self.added: list[tuple[str, object]] = []

    def count(self) -> int:
        """Return remaining source item count."""

        return len(self._items)

    def takeAt(self, index: int) -> _LayoutItem:  # noqa: N802
        """Remove and return one source item."""

        return self._items.pop(index)

    def itemAt(self, index: int) -> _LayoutItem:  # noqa: N802
        """Return one source item without removing it."""

        return self._items[index]

    def addSpacing(self, spacing: int) -> None:  # noqa: N802
        """Record one spacing item."""

        self.added.append(("spacing", spacing))

    def addWidget(self, widget: object) -> None:  # noqa: N802
        """Record one cube widget."""

        self.added.append(("widget", widget))


class _Signal:
    """Record one scroll-signal connection."""

    def __init__(self) -> None:
        """Initialize connected callback storage."""

        self.connected: list[object] = []

    def connect(self, callback: object) -> None:
        """Record the connected callback."""

        self.connected.append(callback)

    def disconnect(self, callback: object) -> None:
        """Discard a previously connected callback when present."""

        if callback in self.connected:
            self.connected.remove(callback)


class _PresetContextRefresh:
    """Record full-projection preset context boundaries."""

    def __init__(self) -> None:
        """Initialize lifecycle call recording."""

        self.begin_projection_calls: list[dict[str, object]] = []
        self.refresh_calls: list[str] = []

    def begin_projection(self, **kwargs: object) -> None:
        """Record one projection boundary."""

        self.begin_projection_calls.append(kwargs)

    def refresh(self, *, reason: str) -> None:
        """Record one post-projection refresh."""

        self.refresh_calls.append(reason)


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_load_all_cubes_reuses_widgets_removes_closed_and_recomputes_once(
    monkeypatch: MonkeyPatch,
) -> None:
    """Full loading should reuse widgets, remove closed aliases, and recompute once."""

    panel_module = _panel_module()
    keep_widget = object()
    old_widget = object()
    new_widget = object()
    layout = _Layout([old_widget, keep_widget])
    removed_widgets: list[object] = []
    built_aliases: list[str] = []
    scrollbar_signal = _Signal()
    scrollbar = SimpleNamespace(valueChanged=scrollbar_signal, value=lambda: 17)
    scroll_updates: list[int] = []
    recompute_calls: list[str] = []
    prompt_calls: list[tuple[str, object]] = []
    widget_refresh_calls: list[str] = []
    cube_keep = SimpleNamespace(buffer={"nodes": {}})
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def build_cube_widget(alias: str, _state: object) -> object:
        """Record and return the widget built for an opened cube."""

        built_aliases.append(alias)
        return new_widget

    panel = SimpleNamespace(
        CUBE_SPACING=panel_module.EditorPanel.CUBE_SPACING,
        cube_widgets={"Keep": keep_widget, "Old": old_widget},
        card_wrappers={("Old", "Node"): object(), ("Keep", "Node"): object()},
        _layout=layout,
        _cube_states=None,
        _stack_order=None,
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: prompt_calls.append(("sanitize", None)),
        reconcile_prompt_link_state=lambda **kwargs: prompt_calls.append(
            ("reconcile", kwargs)
        ),
        sync_prompt_editor_values_from_buffers=lambda: widget_refresh_calls.append(
            "prompt_values"
        ),
        _refresh_link_widgets=lambda: widget_refresh_calls.append("links"),
        _remove_cube_widget_from_layout=removed_widgets.append,
        _build_cube_widget=build_cube_widget,
        _build_behavior_snapshot=lambda **_kwargs: None,
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        cube_sections={"Keep": keep_widget, "Old": old_widget},
        cube_headers={"Old": object()},
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        _on_scroll_updated=lambda value: scroll_updates.append(value),
        refresh_node_behavior_state=lambda **_kwargs: recompute_calls.append(
            "recompute"
        ),
        _preset_context_refresh=_PresetContextRefresh(),
    )
    panel._ordered_buffers = lambda: panel_module.EditorPanel._ordered_buffers(panel)
    panel._refresh_sampler_scheduler_link_state = lambda: (
        panel_module.EditorPanel._refresh_sampler_scheduler_link_state(panel)
    )

    panel_module.EditorPanel.load_all_cubes(
        panel,
        cube_entries=[("Keep", cube_keep), ("New", cube_new)],
        cube_states={"Keep": cube_keep, "New": cube_new},
        stack_order=["Keep", "New"],
    )

    assert removed_widgets == [old_widget]
    assert built_aliases == ["New"]
    assert ("Old", "Node") not in panel.card_wrappers
    assert panel.cube_sections == {"Keep": keep_widget, "New": new_widget}
    assert panel.cube_headers == {}
    assert layout.added == [
        ("spacing", panel_module.EditorPanel.CUBE_SPACING),
        ("widget", keep_widget),
        ("spacing", panel_module.EditorPanel.CUBE_SPACING),
        ("widget", new_widget),
    ]
    assert scroll_updates == [17]
    assert len(scrollbar_signal.connected) == 1
    assert widget_refresh_calls == ["prompt_values", "links"]
    assert prompt_calls == [
        (
            "reconcile",
            {
                "previous_cube_states": None,
                "previous_stack_order": None,
                "cube_states": {"Keep": cube_keep, "New": cube_new},
                "stack_order": ["Keep", "New"],
            },
        )
    ]
    assert recompute_calls == ["recompute"]
