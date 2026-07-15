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

"""Rendered integration harness for the shared workflow/settings toolbar."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    OverrideBehavior,
    OverridePinPolicy,
    ResolvedFieldSpec,
)
from substitute.application.overrides import PinnedOverrideService
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from substitute.presentation.shell.main_window_menu import build_main_window_menu
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "toolbar rendering harness requires a single Qt GUI process",
        allow_module_level=True,
    )


@dataclass(frozen=True)
class ToolbarHarness:
    """Own a rendered toolbar plus its real override manager integration."""

    root: QWidget
    parts: Any
    manager: GlobalOverridesManager

    def close(self) -> None:
        """Close the rendered harness widgets."""

        self.root.close()


class _SnapshotSource:
    """Expose a deterministic editor behavior snapshot to the manager."""

    def __init__(self, snapshot: EditorBehaviorSnapshot) -> None:
        """Store the snapshot returned by the active editor panel."""

        self._snapshot = snapshot

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot:
        """Return the current behavior snapshot."""

        return self._snapshot


class _NodeDefinitionGateway:
    """Return live node definitions for real choice-widget construction."""

    def get_node_definition(self, node_type: str) -> dict[str, object]:
        """Return a minimal Comfy-style node definition for KSampler fields."""

        if node_type != "KSampler":
            return {}
        return {
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": (["er_sde", "euler"], {}),
                        "scheduler": (["simple", "normal"], {}),
                    }
                }
            }
        }

    def get_required_node_definition(self, node_type: str) -> dict[str, object]:
        """Return the node definition or an empty mapping for unknown classes."""

        return self.get_node_definition(node_type)


def _app() -> QApplication:
    """Return the QApplication used by rendered toolbar tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _render_manager_toolbar(width: int) -> ToolbarHarness:
    """Render the production toolbar with a real override manager attached."""

    root = QWidget()
    parts = build_main_window_menu(root, workspace_controller=object())
    parts.menu_bar.setParent(root)
    parts.menu_bar.move(0, 0)
    root.resize(width, 44)
    parts.menu_bar.resize(width, 44)
    root.show()
    parts.menu_bar.show()

    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "sampler_name": {"value": "er_sde", "mode": "global"},
            "scheduler": {"value": "simple", "mode": "global"},
            "seed": {"value": 35092927453489153, "mode": "global"},
        },
    )
    shell = SimpleNamespace(
        menu_bar=parts.menu_bar,
        menu_bar_layout=parts.menu_bar_layout,
        pendingRestartButton=parts.pending_restart_button,
        _active_workspace_route="workflow",
        active_editor_panel=_SnapshotSource(
            _snapshot(
                _field_spec(
                    override_key="sampler_name",
                    field_key="sampler_name",
                    value="er_sde",
                    order=10,
                    field_type="LIST",
                    field_info=[["er_sde", "euler"], {"default": "er_sde"}],
                ),
                _field_spec(
                    override_key="scheduler",
                    field_key="scheduler",
                    value="simple",
                    order=20,
                    field_type="LIST",
                    field_info=[["simple", "normal"], {"default": "simple"}],
                ),
                _field_spec(
                    override_key="seed",
                    field_key="seed",
                    value=35092927453489153,
                    order=30,
                    field_type="INT",
                ),
            )
        ),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        shell,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=_NodeDefinitionGateway(),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = parts.override_dropdown_btn
    manager.sync_state_from_workflow()
    _flush_layout(parts)
    return ToolbarHarness(root=root, parts=parts, manager=manager)


def _snapshot(*specs: ResolvedFieldSpec) -> EditorBehaviorSnapshot:
    """Build an editor snapshot containing representative toolbar candidates."""

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


def _field_spec(
    *,
    override_key: str,
    field_key: str,
    value: object,
    order: int,
    field_type: str,
    field_info: list[object] | None = None,
) -> ResolvedFieldSpec:
    """Build one field spec consumed by the real override manager."""

    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="ksampler",
        class_type="KSampler",
        field_key=field_key,
        field_type=field_type,
        constraints={},
        meta_info={},
        field_info=field_info,
        value=value,
        field_behavior=FieldBehavior(
            field_key=field_key,
            override_behavior=OverrideBehavior(
                override_key=override_key,
                pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                toolbar_order=order,
            ),
        ),
    )


def _flush_layout(parts: Any) -> None:
    """Flush pending Qt layout and paint work before reading geometry."""

    app = _app()
    parts.menu_bar_layout.invalidate()
    parts.menu_bar_layout.activate()
    app.processEvents()
    parts.menu_bar_layout.activate()
    app.processEvents()


def _show_settings_search(harness: ToolbarHarness) -> None:
    """Project the toolbar into settings route state."""

    harness.manager.mainwindow._active_workspace_route = SETTINGS_WORKSPACE_ROUTE
    harness.manager.clear_toolbar_override_controls()
    harness.parts.settings_toolbar_search_box.setVisible(True)
    harness.parts.pending_restart_button.set_collapsed(True)
    harness.parts.pending_restart_button.refresh_toolbar_spacing()
    _flush_layout(harness.parts)


def _show_workflow_restart(harness: ToolbarHarness) -> None:
    """Project the toolbar into workflow route state with restart advisory."""

    harness.manager.mainwindow._active_workspace_route = "workflow"
    harness.parts.settings_toolbar_search_box.hide()
    harness.parts.pending_restart_button.set_count(1)
    harness.parts.pending_restart_button.set_collapsed(False)
    _flush_layout(harness.parts)


def _show_workflow_without_restart(harness: ToolbarHarness) -> None:
    """Project the toolbar into workflow route state without restart advisory."""

    harness.manager.mainwindow._active_workspace_route = "workflow"
    harness.parts.settings_toolbar_search_box.hide()
    harness.parts.pending_restart_button.set_count(0)
    harness.parts.pending_restart_button.set_collapsed(True)
    _flush_layout(harness.parts)


def _rebuild_real_overrides(harness: ToolbarHarness) -> tuple[QWidget, ...]:
    """Run the real override manager and return its mounted widgets in order."""

    harness.manager.rebuild_active_override_controls()
    _flush_layout(harness.parts)
    ordered: list[QWidget] = []
    for key in ("sampler_name", "scheduler", "seed"):
        label, widget = harness.manager._global_override_controls[key]  # noqa: SLF001
        ordered.append(cast(QWidget, label))
        ordered.append(cast(QWidget, widget))
    return tuple(ordered)


def _widget_gap(left: QWidget, right: QWidget) -> int:
    """Return the rendered horizontal gap between two toolbar widgets."""

    return right.geometry().x() - (left.geometry().x() + left.geometry().width())


def _assert_natural_override_gaps(
    widgets: Sequence[QWidget],
    *,
    spacing: int,
) -> None:
    """Assert every real override pair uses only normal layout spacing."""

    gaps = [_widget_gap(left, right) for left, right in zip(widgets, widgets[1:])]
    assert gaps == [spacing] * (len(widgets) - 1)


def test_settings_toolbar_search_is_centered_when_visible() -> None:
    """Settings mode should center the production search widget."""

    _app()
    harness = _render_manager_toolbar(1200)
    try:
        _show_settings_search(harness)

        search = harness.parts.settings_toolbar_search_box.geometry()
        toolbar_center = harness.parts.menu_bar.rect().center().x()

        assert abs(search.center().x() - toolbar_center) <= 1
    finally:
        harness.close()


def test_settings_toolbar_search_stays_centered_with_restart_visible() -> None:
    """Settings search should remain centered while restart advisory is visible."""

    _app()
    harness = _render_manager_toolbar(1200)
    try:
        _show_settings_search(harness)
        harness.parts.pending_restart_button.set_count(1)
        harness.parts.pending_restart_button.set_collapsed(False)
        _flush_layout(harness.parts)

        search = harness.parts.settings_toolbar_search_box.geometry()
        toolbar_center = harness.parts.menu_bar.rect().center().x()

        assert abs(search.center().x() - toolbar_center) <= 1
        assert (
            harness.parts.pending_restart_button.geometry().right()
            == harness.parts.menu_bar.width()
            - harness.parts.menu_bar_layout.contentsMargins().right()
            - 1
        )
    finally:
        harness.close()


def test_settings_route_blocks_real_override_toolbar_rendering() -> None:
    """The real override manager must not mount toolbar widgets in Settings."""

    _app()
    harness = _render_manager_toolbar(1200)
    try:
        _show_workflow_without_restart(harness)
        workflow_widgets = _rebuild_real_overrides(harness)
        assert all(
            harness.parts.menu_bar_layout.indexOf(widget) >= 0
            for widget in workflow_widgets
        )

        _show_settings_search(harness)
        harness.manager.rebuild_active_override_controls()
        _flush_layout(harness.parts)

        assert all(
            harness.parts.menu_bar_layout.indexOf(widget) == -1
            for widget in workflow_widgets
        )
        assert not any(widget.isVisible() for widget in workflow_widgets)
    finally:
        harness.close()


def test_real_override_manager_packs_controls_left_and_restart_right() -> None:
    """The real override manager path should pack controls and right-align restart."""

    _app()
    harness = _render_manager_toolbar(1600)
    try:
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)

        restart_right_gap = (
            harness.parts.menu_bar.width()
            - harness.parts.menu_bar_layout.contentsMargins().right()
            - harness.parts.pending_restart_button.geometry().right()
            - 1
        )

        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
        assert restart_right_gap == 0
        assert _widget_gap(widgets[-1], harness.parts.pending_restart_button) > 200
    finally:
        harness.close()


def test_real_override_harness_catches_missing_absorber_reconciliation() -> None:
    """The harness must fail when no production path restores the right absorber."""

    _app()
    harness = _render_manager_toolbar(1600)
    try:
        _show_workflow_restart(harness)
        leading_spacer = harness.root.findChild(QWidget, "RestartToolbarLeadingSpacer")
        assert leading_spacer is not None
        harness.parts.menu_bar.removeEventFilter(harness.parts.pending_restart_button)
        harness.parts.menu_bar_layout.removeWidget(leading_spacer)
        leading_spacer.hide()
        delattr(cast(Any, harness.manager.mainwindow), "pendingRestartButton")
        widgets = _rebuild_real_overrides(harness)

        with pytest.raises(AssertionError):
            _assert_natural_override_gaps(
                widgets,
                spacing=harness.parts.menu_bar_layout.spacing(),
            )
    finally:
        harness.close()


def test_real_override_manager_starved_toolbar_does_not_spread_controls() -> None:
    """Width pressure should not distribute slack between real override widgets."""

    _app()
    harness = _render_manager_toolbar(600)
    try:
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)
        leading_spacer = harness.root.findChild(QWidget, "RestartToolbarLeadingSpacer")

        assert leading_spacer is not None
        assert harness.parts.menu_bar_layout.indexOf(leading_spacer) == -1
        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
    finally:
        harness.close()


def test_override_controls_yield_without_absorbing_toolbar_slack() -> None:
    """Field controls should shrink when needed without absorbing toolbar slack."""

    _app()
    harness = _render_manager_toolbar(1600)
    try:
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)

        assert all(
            widget.sizePolicy().horizontalPolicy() is QSizePolicy.Policy.Maximum
            for widget in widgets[1::2]
        )
        assert harness.parts.menu_bar_layout.minimumSize().width() <= 600
        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
    finally:
        harness.close()


def test_yielding_controls_preserve_labels_under_width_pressure() -> None:
    """Yielding field controls should prevent avoidable override-label clipping."""

    _app()
    harness = _render_manager_toolbar(600)
    try:
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)
        labels = widgets[::2]
        controls = widgets[1::2]

        label_minimum_widths = tuple(
            label.minimumSizeHint().width() for label in labels
        )

        assert tuple(label.width() for label in labels) == label_minimum_widths
        assert all(
            control.width() >= control.minimumSizeHint().width() for control in controls
        )
        assert harness.parts.menu_bar_layout.minimumSize().width() <= 600
    finally:
        harness.close()


def test_real_override_manager_stays_packed_after_settings_search_hides() -> None:
    """Leaving Settings after rebuild should not leave override widgets spread."""

    _app()
    harness = _render_manager_toolbar(1600)
    try:
        _show_settings_search(harness)
        harness.parts.pending_restart_button.set_count(1)
        harness.parts.pending_restart_button.set_collapsed(False)
        _show_workflow_restart(harness)
        widgets = _rebuild_real_overrides(harness)
        harness.parts.settings_toolbar_search_box.setVisible(False)
        _flush_layout(harness.parts)

        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
        assert _widget_gap(widgets[-1], harness.parts.pending_restart_button) > 200
    finally:
        harness.close()


def test_real_override_manager_recompacts_cached_controls_on_rebuild() -> None:
    """Cached override controls should be repaired before reuse shortcuts return."""

    _app()
    harness = _render_manager_toolbar(1600)
    try:
        _show_workflow_without_restart(harness)
        widgets = _rebuild_real_overrides(harness)
        leading_spacer = harness.root.findChild(QWidget, "RestartToolbarLeadingSpacer")
        assert leading_spacer is not None
        assert harness.parts.menu_bar_layout.indexOf(leading_spacer) >= 0
        assert (
            _widget_gap(widgets[-1], leading_spacer)
            == harness.parts.menu_bar_layout.spacing()
        )
        for widget in widgets:
            widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            if widget.maximumWidth() < 16_777_215:
                widget.setMaximumWidth(16_777_215)
            widget.updateGeometry()
        _flush_layout(harness.parts)

        harness.manager.rebuild_active_override_controls()
        _flush_layout(harness.parts)

        _assert_natural_override_gaps(
            widgets,
            spacing=harness.parts.menu_bar_layout.spacing(),
        )
        for widget in widgets:
            expected_policy = (
                QSizePolicy.Policy.Fixed
                if widget in widgets[::2]
                else QSizePolicy.Policy.Maximum
            )
            assert widget.sizePolicy().horizontalPolicy() is expected_policy
        assert (
            _widget_gap(widgets[-1], leading_spacer)
            == harness.parts.menu_bar_layout.spacing()
        )
    finally:
        harness.close()
