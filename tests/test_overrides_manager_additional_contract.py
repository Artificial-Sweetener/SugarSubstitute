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

"""Additional presentation contracts for the pinned override toolbar manager."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

from substitute.domain.generation.seed_control import SeedControlState, SeedMode
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


class _Signal:
    """Minimal signal stub for widget wiring tests."""

    def __init__(self) -> None:
        self._callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """Store connected callback."""

        self._callbacks.append(callback)

    def emit(self, *args: object) -> None:
        """Invoke stored callbacks."""

        for callback in list(self._callbacks):
            callback(*args)


class _DummyAction:
    """Minimal checked QAction stand-in."""

    def __init__(self, data: dict[str, object], checked: bool) -> None:
        self._data = data
        self._checked = checked

    def data(self) -> dict[str, object]:
        """Return action payload."""

        return self._data

    def isChecked(self) -> bool:
        """Return check state."""

        return self._checked


def _policy_name(policy: object) -> str:
    """Return a stable lower-case name for real or stub Qt size policies."""

    name = getattr(policy, "name", None)
    return str(name if name is not None else policy).lower()


class _DummyLabel:
    """Simple label stub tracked by the toolbar layout."""

    def __init__(self, name: str, parent: object | None = None) -> None:
        self.name = name
        self.deleted = False
        self.visible = False
        self.tooltip = ""
        self.filters: list[object] = []
        self.size_policy: tuple[object, object] | None = None

    def setContentsMargins(self, *_args, **_kwargs) -> None:
        """Ignore label margin updates."""

    def setSizePolicy(self, horizontal: object, vertical: object) -> None:
        """Record toolbar label sizing policy."""

        self.size_policy = (_policy_name(horizontal), _policy_name(vertical))

    def setToolTip(self, tooltip: str) -> None:
        """Record owner tooltip text."""

        self.tooltip = tooltip

    def toolTip(self) -> str:
        """Return owner tooltip text."""

        return self.tooltip

    def installEventFilter(self, tooltip_filter: object) -> None:
        """Record installed tooltip filters."""

        self.filters.append(tooltip_filter)

    def deleteLater(self) -> None:
        """Record disposal."""

        self.deleted = True

    def hide(self) -> None:
        """Record hidden state."""

        self.visible = False

    def show(self) -> None:
        """Record visible state."""

        self.visible = True


class _DummyWidget:
    """Toolbar widget stub with one configurable signal surface."""

    def __init__(self, name: str, signal_name: str = "valueChanged") -> None:
        self.name = name
        self.deleted = False
        self.visible = False
        self.fixed_width: int | None = None
        self.fixed_height: int | None = None
        self.maximum_width: int | None = None
        self.size_policy: tuple[object, object] | None = None
        self.stylesheet: str | None = None
        self.filters: list[object] = []
        setattr(self, signal_name, _Signal())

    def setFixedWidth(self, width: int) -> None:
        """Record fixed width constraints."""

        self.fixed_width = width

    def setFixedHeight(self, height: int) -> None:
        """Record fixed height constraints."""

        self.fixed_height = height

    def setMaximumWidth(self, width: int) -> None:
        """Record maximum width constraints."""

        self.maximum_width = width

    def setSizePolicy(self, horizontal: object, vertical: object) -> None:
        """Record toolbar sizing policy."""

        self.size_policy = (_policy_name(horizontal), _policy_name(vertical))

    def setStyleSheet(self, stylesheet: str) -> None:
        """Record stylesheet constraints."""

        self.stylesheet = stylesheet

    def installEventFilter(self, tooltip_filter: object) -> None:
        """Record installed tooltip filters."""

        self.filters.append(tooltip_filter)

    def deleteLater(self) -> None:
        """Record disposal."""

        self.deleted = True

    def hide(self) -> None:
        """Record hidden state."""

        self.visible = False

    def show(self) -> None:
        """Record visible state."""

        self.visible = True


class _DummyLayout:
    """Minimal menu-bar layout stub used by the manager."""

    def __init__(self) -> None:
        self.widgets: list[object] = []
        self.removed: list[object] = []

    def indexOf(self, widget: object) -> int:
        """Return existing widget index or `-1` when absent."""

        try:
            return self.widgets.index(widget)
        except ValueError:
            return -1

    def insertWidget(self, index: int, widget: object) -> None:
        """Insert one widget into layout order."""

        self.widgets.insert(index, widget)

    def removeWidget(self, widget: object) -> None:
        """Record and remove one widget from layout order."""

        self.removed.append(widget)
        if widget in self.widgets:
            self.widgets.remove(widget)


class _RestartToolbarButton:
    """Record restart toolbar spacing refresh requests."""

    def __init__(self) -> None:
        self.refresh_calls = 0

    def refresh_toolbar_spacing(self) -> None:
        """Record one spacing reconciliation request."""

        self.refresh_calls += 1


class _SnapshotSource:
    """Mutable behavior-snapshot source for toolbar rebuild tests."""

    def __init__(self, snapshot: EditorBehaviorSnapshot) -> None:
        self.snapshot = snapshot

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot:
        """Return the active behavior snapshot."""

        return self.snapshot


def _install_toolbar_view_stubs(
    monkeypatch,
    *,
    build_widget_callback,
    choice_options_callback=None,
) -> None:
    """Install lightweight GUI/module stubs before importing the toolbar manager."""

    sys.modules.pop("substitute.presentation.editor.panel.overrides_controller", None)
    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QAction = type("QAction", (), {})
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    qfw = types.ModuleType("qfluentwidgets")
    qfw.CaptionLabel = _DummyLabel
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)

    field_pipeline_stub = types.ModuleType(
        "substitute.presentation.editor.panel.factories.field_pipeline"
    )
    field_pipeline_stub.LAYOUT_HANDLED = object()
    field_pipeline_stub.build_widget_for_field_spec = build_widget_callback
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.editor.panel.factories.field_pipeline",
        field_pipeline_stub,
    )
    choice_factory_stub = types.ModuleType(
        "substitute.presentation.editor.panel.factories.choice_factory"
    )
    choice_factory_stub.resolve_choice_options_for_field = (
        choice_options_callback
        if choice_options_callback is not None
        else (lambda **_kwargs: ())
    )
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

    tooltips_stub = types.ModuleType("substitute.presentation.widgets.tooltips")

    def _bind_fluent_tooltip(owner, text, *_args, **_kwargs):
        """Record tooltip binding without importing Qt tooltip filters."""

        if hasattr(owner, "setToolTip"):
            owner.setToolTip(text)
        tooltip_filter = object()
        seen: set[int] = set()
        for widget in (owner, *_args):
            if id(widget) in seen:
                continue
            seen.add(id(widget))
            if hasattr(widget, "installEventFilter"):
                widget.installEventFilter(tooltip_filter)

    tooltips_stub.bind_fluent_tooltip = _bind_fluent_tooltip
    tooltips_stub.tooltip_from_field_meta = lambda meta: (
        meta.get("tooltip", "") if isinstance(meta, dict) else ""
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.widgets.tooltips",
        tooltips_stub,
    )


def _field_spec(
    *,
    override_key: str,
    field_key: str,
    value: object,
    order: int,
    pin_policy: OverridePinPolicy = OverridePinPolicy.DEFAULT_PINNED,
    field_type: str = "STRING",
    field_info: object | None = None,
    meta_info: dict[str, object] | None = None,
) -> ResolvedFieldSpec:
    """Build one representative field spec for toolbar manager tests."""

    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="ksampler",
        class_type="KSampler",
        field_key=field_key,
        field_type=field_type,
        constraints={},
        meta_info=dict(meta_info or {}),
        field_info=field_info,
        value=value,
        field_behavior=FieldBehavior(
            field_key=field_key,
            override_behavior=OverrideBehavior(
                override_key=override_key,
                pin_policy=pin_policy,
                toolbar_order=order,
            ),
        ),
    )


def _snapshot(*specs: ResolvedFieldSpec) -> EditorBehaviorSnapshot:
    """Build one snapshot with the provided toolbar candidate specs."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "A": {
                "ksampler": {spec.field_key: spec for spec in specs},
            }
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )


def test_toggle_unpins_override_without_reapplying_default_toolbar_state(
    monkeypatch,
) -> None:
    """Unpinning from the menu should stay local so default-pinned fields remain unpinned."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("seed"),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    local_refresh_calls: list[str] = []
    shell_refresh_calls: list[bool] = []
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": 123, "mode": "global"}},
        global_override_selections={"seed": True},
    )
    mainwindow = SimpleNamespace(
        active_editor_panel=SimpleNamespace(
            current_behavior_snapshot=lambda: _snapshot(
                _field_spec(
                    override_key="seed",
                    field_key="seed",
                    value=123,
                    order=10,
                )
            )
        ),
        get_active_workflow=lambda: workflow,
        refresh_active_workflow_surface=lambda: shell_refresh_calls.append(True),
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.sync_state_from_workflow()
    manager.rebuild_override_menu = lambda: local_refresh_calls.append("menu")
    manager.rebuild_active_override_controls = lambda: local_refresh_calls.append(
        "controls"
    )
    manager.apply_global_overrides = lambda: local_refresh_calls.append("apply")

    manager._on_override_menu_toggled(
        _DummyAction({"override_key": "seed"}, checked=False)
    )

    assert workflow.global_overrides == {}
    assert workflow.global_override_selections == {"seed": False}
    assert local_refresh_calls == ["menu", "controls", "apply"]
    assert shell_refresh_calls == []


def test_unchecked_default_selection_blocks_default_rematerialization(
    monkeypatch,
) -> None:
    """A restored unchecked default-pinned field should remain absent after refresh."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={},
        global_override_selections={"seed": False},
    )
    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value=7,
                order=10,
            )
        )
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=source,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()

    changed = manager.materialize_default_overrides()
    manager.rebuild_active_override_controls()

    assert changed is False
    assert workflow.global_overrides == {}
    assert workflow.global_override_selections == {"seed": False}
    assert manager._global_override_controls == {}


def test_checking_optional_override_persists_selection_and_value(monkeypatch) -> None:
    """Checking an optional candidate should persist menu intent and active value."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("cfg"),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={},
        global_override_selections={},
    )
    mainwindow = SimpleNamespace(
        active_editor_panel=SimpleNamespace(
            current_behavior_snapshot=lambda: _snapshot(
                _field_spec(
                    override_key="cfg",
                    field_key="cfg",
                    value=5.5,
                    order=40,
                    pin_policy=OverridePinPolicy.OPTIONAL,
                    field_type="FLOAT",
                )
            )
        ),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.rebuild_override_menu = lambda: None
    manager.rebuild_active_override_controls = lambda: None
    manager.apply_global_overrides = lambda: None

    manager.sync_state_from_workflow()
    manager._on_override_menu_toggled(_DummyAction({"override_key": "cfg"}, True))

    assert workflow.global_override_selections == {"cfg": True}
    assert workflow.global_overrides == {"cfg": {"value": 5.5, "mode": "global"}}


def test_rebuild_active_override_controls_skips_failed_control_without_clearing_state(
    monkeypatch,
) -> None:
    """One control build failure should not clear unrelated pinned override state."""

    def _build_widget_for_field_spec(*, field_spec, **_kwargs):
        if field_spec.field_key == "scheduler":
            return None
        return _DummyWidget(field_spec.field_key)

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=10,
        ),
        _field_spec(
            override_key="scheduler",
            field_key="scheduler",
            value="karras",
            order=30,
        ),
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "seed": {"value": 7, "mode": "global"},
            "scheduler": {"value": "karras", "mode": "global"},
        },
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()
    manager._toolbar_snapshot = manager._service.build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A"],
        overrides=manager._global_overrides,
    )

    manager.rebuild_active_override_controls()

    assert set(manager._global_overrides) == {"seed", "scheduler"}
    assert set(manager._global_override_controls) == {"seed"}


def test_rebuild_active_override_controls_skips_raising_control_build(
    monkeypatch,
) -> None:
    """One toolbar widget factory exception should not abort the whole rebuild."""

    def _build_widget_for_field_spec(*, field_spec, **_kwargs):
        if field_spec.field_key == "sampler_name":
            raise RuntimeError("missing live choices")
        return _DummyWidget(field_spec.field_key)

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=10,
        ),
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="euler",
            order=20,
        ),
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "seed": {"value": 7, "mode": "global"},
            "sampler_name": {"value": "euler", "mode": "global"},
        },
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()
    manager._toolbar_snapshot = manager._service.build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A"],
        overrides=manager._global_overrides,
    )

    manager.rebuild_active_override_controls()

    assert set(manager._global_overrides) == {"seed", "sampler_name"}
    assert set(manager._global_override_controls) == {"seed"}


def test_rebuild_active_override_controls_refreshes_restart_toolbar_spacing(
    monkeypatch,
) -> None:
    """Override rebuilds should restore the single end absorber for toolbar slack."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="er_sde",
            order=10,
            field_type="LIST",
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"sampler_name": {"value": "er_sde", "mode": "global"}},
    )
    restart_button = _RestartToolbarButton()
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        pendingRestartButton=restart_button,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()

    manager.rebuild_active_override_controls()

    assert restart_button.refresh_calls == 1


def test_rebuild_active_override_controls_refreshes_spacing_when_unchanged(
    monkeypatch,
) -> None:
    """Unchanged override rows still need restart spacer reconciliation."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="er_sde",
            order=10,
            field_type="LIST",
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"sampler_name": {"value": "er_sde", "mode": "global"}},
    )
    restart_button = _RestartToolbarButton()
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        pendingRestartButton=restart_button,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()

    manager.rebuild_active_override_controls()
    manager.rebuild_active_override_controls()

    assert restart_button.refresh_calls == 2


def test_rebuild_active_override_controls_binds_fluent_tooltip_to_label_owner(
    monkeypatch,
) -> None:
    """Toolbar override tooltips should use one QFluent label owner for label and control."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    tooltip_text = "The number of denoise steps."
    snapshot = _snapshot(
        _field_spec(
            override_key="steps",
            field_key="steps",
            value=20,
            order=10,
            field_type="INT",
            meta_info={"tooltip": tooltip_text},
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"steps": {"value": 20, "mode": "global"}},
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()
    manager._toolbar_snapshot = manager._service.build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A"],
        overrides=manager._global_overrides,
    )

    manager.rebuild_active_override_controls()

    label, widget = manager._global_override_controls["steps"]
    assert isinstance(label, _DummyLabel)
    assert isinstance(widget, _DummyWidget)
    assert label.size_policy == ("fixed", "preferred")
    assert widget.size_policy == ("maximum", "fixed")
    assert label.tooltip == tooltip_text
    assert len(label.filters) == 1
    assert widget.filters == label.filters


def test_rebuild_active_override_controls_uses_toolbar_numeric_height(
    monkeypatch,
) -> None:
    """Numeric toolbar overrides should align to the normal toolbar control height."""

    created_widgets: dict[str, _DummyWidget] = {}

    def _build_widget_for_field_spec(*, field_spec, **_kwargs):
        widget = _DummyWidget(field_spec.field_key)
        created_widgets[field_spec.field_key] = widget
        return widget

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="steps",
            field_key="steps",
            value=28,
            order=40,
            field_type="INT",
        ),
        _field_spec(
            override_key="cfg",
            field_key="cfg",
            value=5.5,
            order=50,
            field_type="FLOAT",
        ),
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "steps": {"value": 28, "mode": "global"},
            "cfg": {"value": 5.5, "mode": "global"},
        },
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()

    manager.rebuild_active_override_controls()

    assert created_widgets["steps"].fixed_width is None
    assert created_widgets["cfg"].fixed_width is None
    assert created_widgets["steps"].fixed_height == 32
    assert created_widgets["cfg"].fixed_height == 32
    assert created_widgets["steps"].size_policy == ("maximum", "fixed")
    assert created_widgets["cfg"].size_policy == ("maximum", "fixed")
    assert created_widgets["steps"].stylesheet is None
    assert created_widgets["cfg"].stylesheet is None
    assert created_widgets["steps"].maximum_width is None
    assert created_widgets["cfg"].maximum_width is None


def test_rebuild_active_override_controls_reuses_unchanged_controls(
    monkeypatch,
) -> None:
    """Unchanged pinned override controls should stay mounted across rebuilds."""

    build_calls: list[str] = []

    def _build_widget_for_field_spec(*, field_spec, **_kwargs):
        build_calls.append(field_spec.field_key)
        return _DummyWidget(f"{field_spec.field_key}-{len(build_calls)}")

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=10,
        )
    )
    source = _SnapshotSource(snapshot)
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": 7, "mode": "global"}},
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=source,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()

    manager.rebuild_active_override_controls()
    first_label, first_widget = manager._global_override_controls["seed"]
    manager.rebuild_active_override_controls()

    assert build_calls == ["seed"]
    assert manager._global_override_controls["seed"] == (first_label, first_widget)
    assert layout.widgets == [override_button, first_label, first_widget]
    assert first_label.deleted is False
    assert first_widget.deleted is False


def test_rebuild_active_override_controls_remounts_detached_controls(
    monkeypatch,
) -> None:
    """Tab switches should remount cached controls without rebuilding widgets."""

    build_calls: list[str] = []

    def _build_widget_for_field_spec(*, field_spec, **_kwargs):
        build_calls.append(field_spec.field_key)
        return _DummyWidget(f"{field_spec.field_key}-{len(build_calls)}")

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=10,
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": 7, "mode": "global"}},
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=_SnapshotSource(snapshot),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()
    first_label, first_widget = manager._global_override_controls["seed"]

    manager.detach_override_widgets()
    assert first_label.visible is False
    assert first_widget.visible is False

    manager.rebuild_active_override_controls()

    assert build_calls == ["seed"]
    assert manager._global_override_controls["seed"] == (first_label, first_widget)
    assert layout.widgets == [override_button, first_label, first_widget]
    assert first_label.deleted is False
    assert first_widget.deleted is False
    assert first_label.visible is True
    assert first_widget.visible is True


def test_rebuild_active_override_controls_replaces_choice_fallback_after_live_options(
    monkeypatch,
) -> None:
    """Choice controls should wait for resolved inventories instead of fallbacks."""

    build_calls: list[str] = []

    def _build_widget_for_field_spec(*, field_spec, **_kwargs):
        build_calls.append(field_spec.field_key)
        return _DummyWidget(f"{field_spec.field_key}-{len(build_calls)}")

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
        choice_options_callback=lambda **kwargs: tuple(kwargs["field_info"][0]),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="sampler_name",
                field_key="sampler_name",
                value="euler_ancestral",
                order=10,
                field_type="LIST",
                field_info=["LIST", {"dynamic": True}],
            )
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "sampler_name": {"value": "euler_ancestral", "mode": "global"}
        },
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=source,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()

    assert "sampler_name" not in manager._global_override_controls
    assert build_calls == []

    source.snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="euler_ancestral",
            order=10,
            field_type="LIST",
            field_info=[["euler", "euler_ancestral", "heun"], {"default": "euler"}],
        )
    )
    manager.rebuild_active_override_controls()

    assert build_calls == ["sampler_name"]
    assert "sampler_name" in manager._global_override_controls
    label, widget = manager._global_override_controls["sampler_name"]
    assert label.size_policy == ("fixed", "preferred")
    assert widget.size_policy == ("maximum", "fixed")
    assert widget.maximum_width == 180


def test_rebuild_active_override_controls_removes_inactive_controls(
    monkeypatch,
) -> None:
    """Controls no longer active in the toolbar snapshot should be disposed."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value=7,
                order=10,
            ),
            _field_spec(
                override_key="cfg",
                field_key="cfg",
                value=5.5,
                order=20,
                field_type="FLOAT",
            ),
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "seed": {"value": 7, "mode": "global"},
            "cfg": {"value": 5.5, "mode": "global"},
        },
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=source,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()
    removed_label, removed_widget = manager._global_override_controls["cfg"]

    workflow.global_overrides = {"seed": {"value": 7, "mode": "global"}}
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()

    assert set(manager._global_override_controls) == {"seed"}
    assert removed_label.deleted is True
    assert removed_widget.deleted is True
    assert removed_label not in layout.widgets
    assert removed_widget not in layout.widgets


def test_rebuild_active_override_controls_reorders_reused_controls(
    monkeypatch,
) -> None:
    """Reused controls should be moved to the active snapshot order."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value=7,
                order=10,
            ),
            _field_spec(
                override_key="cfg",
                field_key="cfg",
                value=5.5,
                order=20,
                field_type="FLOAT",
            ),
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "seed": {"value": 7, "mode": "global"},
            "cfg": {"value": 5.5, "mode": "global"},
        },
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=source,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()
    seed_control = manager._global_override_controls["seed"]
    cfg_control = manager._global_override_controls["cfg"]

    source.snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=30,
        ),
        _field_spec(
            override_key="cfg",
            field_key="cfg",
            value=5.5,
            order=10,
            field_type="FLOAT",
        ),
    )
    manager.rebuild_active_override_controls()

    assert manager._global_override_controls["seed"] == seed_control
    assert manager._global_override_controls["cfg"] == cfg_control
    assert layout.widgets == [
        override_button,
        cfg_control[0],
        cfg_control[1],
        seed_control[0],
        seed_control[1],
    ]


def test_rebuild_active_override_controls_inserts_after_layout_anchor(
    monkeypatch,
) -> None:
    """Active controls should follow the under-orb layout anchor when present."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value=7,
                order=10,
            ),
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": 7, "mode": "global"}},
    )
    anchor = object()
    override_button = SimpleNamespace(
        property=lambda name: anchor if name == "layoutAnchorWidget" else None
    )
    layout = _DummyLayout()
    layout.widgets.append(anchor)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=source,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()

    seed_label, seed_widget = manager._global_override_controls["seed"]
    assert layout.widgets == [anchor, seed_label, seed_widget]


def test_rebuild_active_override_controls_replaces_changed_field_contract(
    monkeypatch,
) -> None:
    """A changed field render contract should replace only the affected control."""

    build_calls: list[str] = []

    def _build_widget_for_field_spec(*, field_spec, **_kwargs):
        build_calls.append(field_spec.field_type)
        return _DummyWidget(f"{field_spec.field_key}-{field_spec.field_type}")

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value="7",
                order=10,
            )
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": "7", "mode": "global"}},
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=source,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()
    old_label, old_widget = manager._global_override_controls["seed"]

    source.snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=10,
            field_type="INT",
        )
    )
    workflow.global_overrides = {"seed": {"value": 7, "mode": "global"}}
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()

    assert build_calls == ["STRING", "INT"]
    assert manager._global_override_controls["seed"] != (old_label, old_widget)
    assert old_label.deleted is True
    assert old_widget.deleted is True


def test_seed_override_mode_round_trips_without_overwriting_override_mode(
    monkeypatch,
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
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
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


def test_apply_global_overrides_falls_back_to_hidden_tuple_keys(monkeypatch) -> None:
    """Fallback hidden-field updates should use resolved tuple keys when recompute fails."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("seed"),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=5,
            order=10,
        )
    )
    hidden_calls: list[set[object]] = []
    cube = SimpleNamespace(
        buffer={"nodes": {"ksampler": {"inputs": {"seed": 0}}}},
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={"seed": {"value": 5, "mode": "global"}},
    )
    panel = SimpleNamespace(
        current_behavior_snapshot=lambda: snapshot,
        refresh_node_behavior_state=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("boom")
        ),
        set_hidden_field_keys=lambda keys: hidden_calls.append(set(keys)),
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
    manager.sync_state_from_workflow()

    manager.apply_global_overrides()

    assert cube.buffer["nodes"]["ksampler"]["inputs"]["seed"] == 5
    assert hidden_calls == [{("A", "ksampler", "seed")}]


def test_apply_global_overrides_rebuilds_snapshot_after_buffer_change(
    monkeypatch,
) -> None:
    """Changed override writes should force a fresh behavior snapshot refresh."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("sampler"),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="",
            order=20,
        )
    )
    refresh_calls: list[dict[str, object]] = []
    cube = SimpleNamespace(
        buffer={"nodes": {"ksampler": {"inputs": {"sampler_name": ""}}}},
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={
            "sampler_name": {"value": "euler_ancestral", "mode": "global"}
        },
    )
    panel = SimpleNamespace(
        current_behavior_snapshot=lambda: snapshot,
        refresh_node_behavior_state=lambda **kwargs: refresh_calls.append(kwargs),
    )
    manager = GlobalOverridesManager(
        SimpleNamespace(
            active_editor_panel=panel, get_active_workflow=lambda: workflow
        ),
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.sync_state_from_workflow()

    manager.apply_global_overrides(use_cached_behavior_snapshot=True)

    assert cube.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == (
        "euler_ancestral"
    )
    assert refresh_calls == [
        {"reason": "global_override_changed", "use_cached_snapshot": False}
    ]


def test_apply_global_overrides_reuses_cached_snapshot_when_buffers_do_not_change(
    monkeypatch,
) -> None:
    """Unchanged override writes may keep the caller-requested cached snapshot path."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("sampler"),
    )
    from substitute.presentation.editor.panel.overrides_controller import (
        GlobalOverridesManager,
    )

    snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="euler_ancestral",
            order=20,
        )
    )
    refresh_calls: list[dict[str, object]] = []
    cube = SimpleNamespace(
        buffer={"nodes": {"ksampler": {"inputs": {"sampler_name": "euler_ancestral"}}}},
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={
            "sampler_name": {"value": "euler_ancestral", "mode": "global"}
        },
    )
    panel = SimpleNamespace(
        current_behavior_snapshot=lambda: snapshot,
        refresh_node_behavior_state=lambda **kwargs: refresh_calls.append(kwargs),
    )
    manager = GlobalOverridesManager(
        SimpleNamespace(
            active_editor_panel=panel, get_active_workflow=lambda: workflow
        ),
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.sync_state_from_workflow()

    manager.apply_global_overrides(use_cached_behavior_snapshot=True)

    assert cube.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == (
        "euler_ancestral"
    )
    assert refresh_calls == [
        {"reason": "global_override_changed", "use_cached_snapshot": True}
    ]
