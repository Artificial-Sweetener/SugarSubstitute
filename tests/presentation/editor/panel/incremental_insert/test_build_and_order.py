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

"""Test incremental cube-widget construction and stack ordering."""

from __future__ import annotations

from __future__ import annotations
import importlib
from types import SimpleNamespace
from typing import Any, cast
import pytest
import substitute.presentation.editor.panel.hidden_build_scheduler as hidden_build_scheduler
from tests.presentation.editor.panel.projection_support import (
    _BuildSession,
    _Layout,
    _LayoutItem,
    _Signal,
    _Widget,
)


def test_insert_cube_builds_new_widget_and_repopulates_layout_in_stack_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental cube insert should keep physical layout aligned to stack order."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(lambda _msec, _owner, callback: callback()),
    )

    existing_widget = _Widget()
    new_widget = _Widget()
    layout = _Layout([_LayoutItem(widget=existing_widget)])
    built_aliases: list[str] = []
    scroll_signal = _Signal()
    scrollbar = SimpleNamespace(valueChanged=scroll_signal, value=lambda: 3)
    registry_calls: list[str] = []
    motion_calls: list[tuple[str, object]] = []

    def prepare_motion(
        alias: str,
        *,
        replace_node_cards: bool = False,
    ) -> int:
        """Record pre-commit capture for the inserted cube."""

        motion_calls.append(
            ("prepare", {"alias": alias, "replace_node_cards": replace_node_cards})
        )
        return 7

    def present_motion(**kwargs: object) -> bool:
        """Record post-commit presentation for the inserted cube."""

        motion_calls.append(("present", kwargs))
        return True

    def cancel_motion(**kwargs: object) -> None:
        """Record a requested transition cancellation."""

        motion_calls.append(("cancel", kwargs))

    refresh_kwargs: list[dict[str, object]] = []

    cube_existing = SimpleNamespace(buffer={"nodes": {}})
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def _begin_build_cube_widget(alias: str, _state: object) -> _BuildSession:
        built_aliases.append(alias)
        return _BuildSession(new_widget)

    def _record_visibility(**kwargs: object) -> None:
        registry_calls.append("visibility")
        refresh_kwargs.append(kwargs)

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={"Existing": existing_widget},
        cube_sections={"Existing": existing_widget},
        cube_headers={},
        card_wrappers={},
        _cube_states={"Existing": cube_existing},
        _stack_order=["Existing"],
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _build_cube_widget=lambda _alias, _state: new_widget,
        _begin_build_cube_widget=_begin_build_cube_widget,
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        begin_projection_prompt_context=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("incremental insert should not start prompt context")
        ),
        clear_projection_prompt_context=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("incremental insert should not clear prompt context")
        ),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=_record_visibility,
        _surface_motion=SimpleNamespace(
            prepare_cube_insert=prepare_motion,
            present_cube_insert=present_motion,
            cancel=cancel_motion,
        ),
    )

    mod.EditorPanelProjectionCoordinator(panel).insert_cube(
        "New",
        cube_new,
        cube_states={"Existing": cube_existing, "New": cube_new},
        stack_order=["Existing", "New"],
        motion_requested=True,
    )

    assert built_aliases == ["New"]
    assert existing_widget.parents == []
    assert panel.cube_widgets == {"Existing": existing_widget, "New": new_widget}
    assert panel.cube_sections["New"] is new_widget
    assert layout.added == [
        ("spacing", 8),
        ("widget", existing_widget),
        ("spacing", 8),
        ("widget", new_widget),
    ]
    assert registry_calls == [
        "hydrate",
        "reconcile",
        "snapshot",
        "sampler_scheduler",
        "scroll",
        "prompt_values:New",
        "links:New",
        "visibility",
    ]
    assert refresh_kwargs == [{"reason": "cube_added", "use_cached_snapshot": True}]
    assert motion_calls == [
        ("prepare", {"alias": "New", "replace_node_cards": False}),
        (
            "present",
            {
                "generation": 7,
                "cube_alias": "New",
                "cube_widget": new_widget,
            },
        ),
    ]


def test_insert_cube_honors_reordered_placeholder_stack_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental insert should place the completed cube at its stack-order slot."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(lambda _msec, _owner, callback: callback()),
    )

    existing_widget = _Widget()
    new_widget = _Widget()
    layout = _Layout([_LayoutItem(widget=existing_widget)])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 5)
    registry_calls: list[str] = []

    cube_existing = SimpleNamespace(buffer={"nodes": {}})
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={"Existing": existing_widget},
        cube_sections={"Existing": existing_widget},
        cube_headers={},
        card_wrappers={},
        _cube_states={"Existing": cube_existing},
        _stack_order=["Existing"],
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _build_cube_widget=lambda _alias, _state: new_widget,
        _begin_build_cube_widget=lambda _alias, _state: _BuildSession(new_widget),
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )

    mod.EditorPanelProjectionCoordinator(panel).insert_cube(
        "New",
        cube_new,
        cube_states={"Existing": cube_existing, "New": cube_new},
        stack_order=["New", "Existing"],
    )

    assert layout.added == [
        ("spacing", 8),
        ("widget", new_widget),
        ("spacing", 8),
        ("widget", existing_widget),
    ]
    assert list(panel.cube_sections) == ["New", "Existing"]


def test_insert_cube_adds_silent_batch_insert_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silent incremental inserts should add the cube directly to the layout."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(lambda _msec, _owner, callback: callback()),
    )

    new_widget = _Widget()
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    registry_calls: list[str] = []
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states={},
        _stack_order=[],
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _build_cube_widget=lambda _alias, _state: new_widget,
        _begin_build_cube_widget=lambda _alias, _state: _BuildSession(new_widget),
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )

    mod.EditorPanelProjectionCoordinator(panel).insert_cube(
        "New",
        cube_new,
        cube_states={"New": cube_new},
        stack_order=["New"],
    )

    assert layout.added == [("spacing", 8), ("widget", new_widget)]
