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

"""Verify override SeedBox mode persistence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.overrides import PinnedOverrideService
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)
from tests.presentation.editor.panel.overrides.support import (
    _DummyLayout,
    _Signal,
    _SnapshotSource,
    _field_spec,
    _install_toolbar_view_stubs,
    _snapshot,
)


def test_seed_override_mode_round_trips_without_overwriting_override_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Override SeedBox lock mode should persist outside global override mode."""

    class SeedBox:
        """SeedBox-shaped toolbar double for override mode persistence."""

        def __init__(self) -> None:
            """Initialize mode state and signals."""

            self.mode_value = "random"
            self.modeChanged = _Signal()
            self.valueChanged = _Signal()

        def setMode(self, mode: str) -> None:  # noqa: N802
            """Record mode and emit only for user-visible changes."""

            if self.mode_value == mode:
                return
            self.mode_value = mode
            self.modeChanged.emit(mode)

    widget = SeedBox()
    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: widget,
    )
    autosaves: list[str] = []
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": 123, "mode": "global"}},
        global_override_selections={"seed": True},
        override_control_states={"seed": SeedControlState(SeedMode.FIXED)},
    )
    layout = _DummyLayout()
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=_SnapshotSource(
            _snapshot(
                _field_spec(
                    override_key="seed",
                    field_key="seed",
                    value=123,
                    order=10,
                    field_type="INT",
                )
            )
        ),
        get_active_workflow=lambda: workflow,
        request_session_autosave=lambda: autosaves.append("autosave"),
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()

    assert widget.mode_value == "fixed"

    widget.setMode("random")

    assert workflow.override_control_states["seed"].mode == SeedMode.RANDOM
    assert workflow.global_overrides["seed"]["mode"] == "global"
    assert autosaves == ["autosave"]
