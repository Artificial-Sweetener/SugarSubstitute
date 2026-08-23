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

"""Test projection lifecycle cube rename behavior."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch


class _Widget:
    """Expose Qt-style dynamic properties for renamed widget metadata."""

    def __init__(self, properties: dict[str, object] | None = None) -> None:
        """Initialize widget properties."""

        self._properties = dict(properties or {})

    def property(self, name: str) -> object | None:
        """Return one dynamic property."""

        return self._properties.get(name)

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        """Record one dynamic property update."""

        self._properties[name] = value


class _Label:
    """Record the visible cube title."""

    def __init__(self) -> None:
        """Initialize title state."""

        self.text = ""

    def setText(self, text: str) -> None:  # noqa: N802
        """Record title text."""

        self.text = text


class _Combo:
    """Record cleanup of obsolete link selector widgets."""

    def __init__(self) -> None:
        """Initialize deletion state."""

        self.parents: list[object | None] = []
        self.deleted = False

    def setParent(self, parent: object | None) -> None:  # noqa: N802
        """Record a parent assignment."""

        self.parents.append(parent)

    def deleteLater(self) -> None:  # noqa: N802
        """Record deferred deletion."""

        self.deleted = True


def _module(path: str) -> ModuleType:
    """Return one production editor-panel module."""

    return importlib.import_module(path)


def test_rename_cube_updates_maps_cleans_widgets_and_refreshes_links(
    monkeypatch: MonkeyPatch,
) -> None:
    """Cube rename should migrate maps and update all live link references."""

    panel_module = _module("substitute.presentation.editor.panel.view")
    coordinator_module = _module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    lifecycle_module = _module(
        "substitute.presentation.editor.panel.projection_lifecycle"
    )
    registry_module = _module("substitute.presentation.editor.panel.cube_registry")
    monkeypatch.setattr(panel_module, "isValid", lambda _object: True)
    monkeypatch.setattr(
        registry_module,
        "cube_section_title",
        lambda alias, _cube_state: f"Pretty {alias}",
    )

    link_calls: list[tuple[str, object]] = []
    for name, reference_label in (
        ("update_prompt_link_references_on_rename", "prompt_refs"),
        ("update_sampler_link_references_on_rename", "sampler_refs"),
        ("update_scheduler_link_references_on_rename", "scheduler_refs"),
        ("update_node_link_references_on_rename", "node_refs"),
    ):
        monkeypatch.setattr(
            lifecycle_module,
            name,
            lambda buffers, old, new, reference_label=reference_label: (
                link_calls.append((reference_label, (buffers, old, new)))
            ),
        )

    label = _Label()
    stale_node = _Combo()
    stale_sampler = _Combo()
    stale_scheduler = _Combo()
    card_wrapper = _Widget()
    row_widget = _Widget(
        {"input_metadata": {"cube_alias": "old", "node_name": "n", "key": "k"}}
    )
    column_widget = _Widget(
        {"input_metadata": {"cube_alias": "old", "node_name": "n", "key": "k"}}
    )
    old_cube = SimpleNamespace(buffer={"nodes": {}})
    other_cube = SimpleNamespace(buffer={"nodes": {}})
    registry_calls: list[str] = []
    cube_section = object()
    panel = SimpleNamespace(
        cube_headers={"old": label},
        cube_positions={"old": 12},
        cube_widgets={"old": object()},
        cube_sections={"old": cube_section},
        _cube_visibility_btns={"old": object()},
        _cube_visibility_menus={"old": object()},
        _cube_states={"old": old_cube, "other": other_cube},
        _stack_order=["old", "other"],
        node_definition_gateway=object(),
        node_link_widgets={("old", "vectorscopecc"): stale_node},
        node_link_title_surfaces={("old", "vectorscopecc"): object()},
        sampler_link_widgets={("old", "ksampler"): stale_sampler},
        scheduler_link_widgets={("old", "ksampler"): stale_scheduler},
        row_widgets={("old", "n", "k"): (None, row_widget)},
        col_widgets={("old", "n", "k"): (None, column_widget, object())},
        card_wrappers={("old", "n"): card_wrapper},
        meta_registry=SimpleNamespace(
            rename_node_link_alias=lambda old, new: registry_calls.append(
                f"node_rename:{old}->{new}"
            ),
            update_node_link_widgets=lambda: registry_calls.append("node"),
            update_sampler_link_widgets=lambda: registry_calls.append("sampler"),
            update_scheduler_link_widgets=lambda: registry_calls.append("scheduler"),
        ),
        sanitize_prompt_link_state=lambda: registry_calls.append("prompt_state"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "recompute"
        ),
    )
    panel._ordered_buffers = lambda: panel_module.EditorPanel._ordered_buffers(panel)
    panel._refresh_sampler_scheduler_link_state = lambda: (
        panel_module.EditorPanel._refresh_sampler_scheduler_link_state(panel)
    )
    panel._refresh_link_widgets = lambda: (
        panel_module.EditorPanel._refresh_link_widgets(panel)
    )
    panel._cube_registry_controller = lambda: registry_module.EditorCubeRegistry(panel)

    coordinator_module.EditorPanelProjectionCoordinator(panel).rename_cube("old", "new")

    assert label.text == "Pretty new"
    assert "old" not in panel.cube_headers
    assert panel.cube_headers["new"] is label
    assert "old" not in panel.cube_sections
    assert panel.cube_sections["new"] is cube_section
    assert panel._stack_order == ["new", "other"]
    assert "old" not in panel._cube_states
    assert ("new", "n", "k") in panel.row_widgets
    assert ("old", "n", "k") not in panel.row_widgets
    assert _input_metadata_alias(row_widget) == "new"
    assert ("new", "n", "k") in panel.col_widgets
    assert ("old", "n", "k") not in panel.col_widgets
    assert _input_metadata_alias(column_widget) == "new"
    assert ("new", "n") in panel.card_wrappers
    assert ("old", "n") not in panel.card_wrappers
    assert card_wrapper.property("cube_alias") == "new"
    assert ("new", "ksampler") in panel.sampler_link_widgets
    assert ("old", "ksampler") not in panel.sampler_link_widgets
    assert ("new", "ksampler") in panel.scheduler_link_widgets
    assert ("old", "ksampler") not in panel.scheduler_link_widgets
    assert stale_sampler.deleted is False
    assert stale_scheduler.deleted is False
    assert registry_calls == [
        "node_rename:old->new",
        "prompt_state",
        "node",
        "sampler",
        "scheduler",
        "recompute",
    ]
    assert [name for name, _payload in link_calls] == [
        "prompt_refs",
        "node_refs",
        "sampler_refs",
        "scheduler_refs",
    ]


def _input_metadata_alias(widget: _Widget) -> str:
    """Return the renamed alias from widget input metadata."""

    metadata = widget.property("input_metadata")
    assert isinstance(metadata, dict)
    alias = metadata["cube_alias"]
    assert isinstance(alias, str)
    return alias
