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

"""Presentation contract tests for the pinned override menu renderer."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    OverrideBehavior,
    OverridePinPolicy,
    ResolvedFieldSpec,
)
from substitute.application.overrides import PinnedOverrideService
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)


class _DummyAction:
    """Minimal QAction stand-in for override menu tests."""

    def __init__(self, text: str, parent: object | None = None) -> None:
        self._text = text
        self._checkable = False
        self._checked = False
        self._data: dict[str, object] | None = None

    def setCheckable(self, value: bool) -> None:
        """Record checkable state."""

        self._checkable = bool(value)

    def setChecked(self, value: bool) -> None:
        """Record checked state."""

        self._checked = bool(value)

    def setData(self, data: dict[str, object]) -> None:
        """Store action payload."""

        self._data = data

    def data(self) -> dict[str, object] | None:
        """Return stored action payload."""

        return self._data

    def isChecked(self) -> bool:
        """Return the stored checked state."""

        return self._checked

    def text(self) -> str:
        """Return the action label."""

        return self._text


class _DummyMenu:
    """Minimal action collection used by the override menu renderer."""

    def __init__(self) -> None:
        self._actions: list[_DummyAction] = []

    def clear(self) -> None:
        """Drop all actions."""

        self._actions.clear()

    def addAction(self, action: _DummyAction) -> None:
        """Append one action."""

        self._actions.append(action)

    def actions(self) -> list[_DummyAction]:
        """Return stored actions."""

        return list(self._actions)


class _DummyButton:
    """Minimal toolbar button stub."""

    def __init__(self) -> None:
        self.tooltip: str | None = None

    def setToolTip(self, tooltip: str) -> None:
        """Record tooltip updates."""

        self.tooltip = tooltip


def _install_override_menu_stubs(monkeypatch) -> None:
    """Install lightweight GUI/module stubs before importing the toolbar view."""

    sys.modules.pop("substitute.presentation.editor.panel.overrides_controller", None)
    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QAction = _DummyAction
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    qfw = types.ModuleType("qfluentwidgets")

    class _CaptionLabel:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def setContentsMargins(self, *_args, **_kwargs) -> None:
            pass

    qfw.CaptionLabel = _CaptionLabel
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)

    workflow_tabs_stub = types.ModuleType(
        "substitute.presentation.workflows.workflow_tabs_view"
    )
    workflow_tabs_stub.SETTINGS_WORKSPACE_ROUTE = "settings"
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.workflows.workflow_tabs_view",
        workflow_tabs_stub,
    )

    renderer_stub = types.ModuleType(
        "substitute.presentation.widgets.qfluent_menu_renderer"
    )

    class _QFluentMenuRenderer:
        """Populate dummy menus from shared menu entries."""

        def __init__(self, *, parent: object) -> None:
            """Accept the renderer parent for API compatibility."""

            self.parent = parent

        def populate_menu(self, menu: _DummyMenu, entries: tuple[object, ...]) -> None:
            """Append dummy actions for menu item entries."""

            for entry in entries:
                label = getattr(entry, "label", None)
                if not isinstance(label, str):
                    continue
                action = _DummyAction(label, menu)
                action.setCheckable(bool(getattr(entry, "checkable", False)))
                action.setChecked(bool(getattr(entry, "checked", False)))
                action.setData(getattr(entry, "data", None))
                menu.addAction(action)

    renderer_stub.QFluentMenuRenderer = _QFluentMenuRenderer
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.widgets.qfluent_menu_renderer",
        renderer_stub,
    )

    field_pipeline_stub = types.ModuleType(
        "substitute.presentation.editor.panel.factories.field_pipeline"
    )
    field_pipeline_stub.LAYOUT_HANDLED = object()
    field_pipeline_stub.build_widget_for_field_spec = lambda **_kwargs: None
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.factories.field_pipeline",
        field_pipeline_stub,
    )
    choice_factory_stub = types.ModuleType(
        "substitute.presentation.editor.panel.factories.choice_factory"
    )
    choice_factory_stub.resolve_choice_options_for_field = lambda **_kwargs: ()
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.factories.choice_factory",
        choice_factory_stub,
    )

    field_state_stub = types.ModuleType(
        "substitute.presentation.editor.panel.field_state_controller"
    )
    field_state_stub.EditorPanelFieldStateController = type(
        "EditorPanelFieldStateController",
        (),
        {
            "__init__": lambda self, *_args, **_kwargs: None,
            "bind_node_widget_state": lambda self, *_args, **_kwargs: None,
        },
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.field_state_controller",
        field_state_stub,
    )
    model_choice_stub = types.ModuleType(
        "substitute.presentation.editor.panel.model_choice_snapshot_controller"
    )
    model_choice_stub.PanelModelChoiceSnapshotController = type(
        "PanelModelChoiceSnapshotController",
        (),
        {},
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.model_choice_snapshot_controller",
        model_choice_stub,
    )


def _field_spec(
    *,
    cube_alias: str,
    node_name: str,
    field_key: str,
    value: object,
    override_key: str,
    toolbar_order: int,
    pin_policy: OverridePinPolicy = OverridePinPolicy.DEFAULT_PINNED,
) -> ResolvedFieldSpec:
    """Build one minimal resolved field spec for menu rendering tests."""

    return ResolvedFieldSpec(
        cube_alias=cube_alias,
        node_name=node_name,
        class_type="KSampler",
        field_key=field_key,
        field_type="STRING",
        constraints={},
        meta_info={},
        field_info=None,
        value=value,
        field_behavior=FieldBehavior(
            field_key=field_key,
            override_behavior=OverrideBehavior(
                override_key=override_key,
                pin_policy=pin_policy,
                toolbar_order=toolbar_order,
            ),
        ),
    )


def test_rebuild_override_menu_uses_behavior_snapshot_candidates(monkeypatch) -> None:
    """Override menu entries should come from field specs, not live editor widget maps."""

    _install_override_menu_stubs(monkeypatch)
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "A": {
                "ksampler": {
                    "seed": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        field_key="seed",
                        value=7,
                        override_key="seed",
                        toolbar_order=10,
                    ),
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        toolbar_order=20,
                    ),
                    "scheduler": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        field_key="scheduler",
                        value="karras",
                        override_key="scheduler",
                        toolbar_order=30,
                    ),
                    "steps": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        field_key="steps",
                        value=20,
                        override_key="steps",
                        toolbar_order=40,
                        pin_policy=OverridePinPolicy.OPTIONAL,
                    ),
                    "cfg": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        field_key="cfg",
                        value=7.0,
                        override_key="cfg",
                        toolbar_order=50,
                        pin_policy=OverridePinPolicy.OPTIONAL,
                    ),
                }
            }
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    workflow = SimpleNamespace(stack_order=["A"], global_overrides={})
    panel = SimpleNamespace(
        current_behavior_snapshot=lambda: behavior_snapshot,
        row_widgets={"ignored": object()},
        col_widgets={"ignored": object()},
    )
    mainwindow = SimpleNamespace(
        active_editor_panel=panel,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager._global_override_menu = _DummyMenu()
    manager.override_dropdown_btn = _DummyButton()

    manager.sync_state_from_workflow()
    manager.materialize_default_overrides()
    manager.rebuild_override_menu()

    actions = manager._global_override_menu.actions()
    action_keys: list[object] = []
    checked_by_key: dict[object, bool] = {}
    for action in actions:
        action_data = action.data()
        assert action_data is not None
        action_keys.append(action_data["override_key"])
        checked_by_key[action_data["override_key"]] = action.isChecked()

    assert action_keys == [
        "seed",
        "sampler_name",
        "scheduler",
        "steps",
        "cfg",
    ]
    assert checked_by_key == {
        "seed": True,
        "sampler_name": True,
        "scheduler": True,
        "steps": False,
        "cfg": False,
    }
    assert manager.override_dropdown_btn.tooltip == "Set Global Override"
