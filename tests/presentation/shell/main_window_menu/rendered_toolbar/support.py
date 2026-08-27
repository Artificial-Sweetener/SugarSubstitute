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

"""Build and settle the production toolbar with real override controls."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    FieldPresentation,
    OverrideBehavior,
    OverridePinPolicy,
    ResolvedFieldSpec,
)
from substitute.application.overrides import PinnedOverrideService
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from substitute.presentation.shell.main_window_menu import build_main_window_menu
from substitute.presentation.widgets import SeedBox
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


@dataclass
class ToolbarHarness:
    """Own a rendered toolbar plus its real override manager integration."""

    application: QApplication
    root: QWidget
    parts: Any
    manager: GlobalOverridesManager
    snapshot_source: SnapshotSource

    def settle_layout(self) -> None:
        """Advance Qt until the toolbar layout geometry stops changing."""

        previous: tuple[object, ...] | None = None
        for _ in range(16):
            self.parts.menu_bar_layout.invalidate()
            self.parts.menu_bar_layout.activate()
            self.application.processEvents()
            current = self._layout_signature()
            if current == previous:
                return
            previous = current
        raise AssertionError("rendered toolbar layout did not settle")

    def close(self) -> None:
        """Dispose override state and destroy the native toolbar root exactly."""

        self.manager.dispose()
        destroy_qt_object(self.root)

    def _layout_signature(self) -> tuple[object, ...]:
        """Return observable geometry for every toolbar layout item."""

        items: list[object] = [
            self.parts.menu_bar.size(),
            self.parts.menu_bar_layout.minimumSize(),
        ]
        for index in range(self.parts.menu_bar_layout.count()):
            item = self.parts.menu_bar_layout.itemAt(index)
            geometry = item.geometry()
            widget = item.widget()
            items.append(
                (
                    geometry.x(),
                    geometry.y(),
                    geometry.width(),
                    geometry.height(),
                    widget.isVisible() if widget is not None else None,
                )
            )
        return tuple(items)


class SnapshotSource:
    """Expose a deterministic editor behavior snapshot to the manager."""

    def __init__(self, snapshot: EditorBehaviorSnapshot) -> None:
        """Store the snapshot returned by the active editor panel."""

        self._snapshot = snapshot

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot:
        """Return the current behavior snapshot."""

        return self._snapshot

    def set_snapshot(self, snapshot: EditorBehaviorSnapshot) -> None:
        """Replace the active behavior snapshot for document-switch tests."""

        self._snapshot = snapshot


class NodeDefinitionGateway:
    """Return live node definitions for real choice-widget construction."""

    def get_node_definition(self, node_type: str) -> dict[str, object]:
        """Return a minimal Comfy-style KSampler definition."""

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


def render_manager_toolbar(
    width: int,
    *,
    seed_field_key: str = "seed",
) -> ToolbarHarness:
    """Render the production toolbar with a real override manager attached."""

    application = ensure_qt_application()
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
    snapshot_source = SnapshotSource(override_snapshot(seed_field_key))
    shell = SimpleNamespace(
        menu_bar=parts.menu_bar,
        menu_bar_layout=parts.menu_bar_layout,
        pendingRestartButton=parts.pending_restart_button,
        _active_workspace_route="workflow",
        active_editor_panel=snapshot_source,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        shell,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=NodeDefinitionGateway(),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = parts.override_dropdown_btn
    manager.sync_state_from_workflow()
    harness = ToolbarHarness(
        application=application,
        root=root,
        parts=parts,
        manager=manager,
        snapshot_source=snapshot_source,
    )
    harness.settle_layout()
    return harness


def override_snapshot(seed_field_key: str) -> EditorBehaviorSnapshot:
    """Return equivalent override behavior with a selected Comfy seed alias."""

    return snapshot(
        field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="er_sde",
            order=10,
            field_type="LIST",
            field_info=[["er_sde", "euler"], {"default": "er_sde"}],
        ),
        field_spec(
            override_key="scheduler",
            field_key="scheduler",
            value="simple",
            order=20,
            field_type="LIST",
            field_info=[["simple", "normal"], {"default": "simple"}],
        ),
        field_spec(
            override_key="seed",
            field_key=seed_field_key,
            value=35092927453489153,
            order=30,
            field_type="INT",
            presentation=FieldPresentation.SEED_BOX,
        ),
    )


def snapshot(*specs: ResolvedFieldSpec) -> EditorBehaviorSnapshot:
    """Build an editor snapshot containing representative toolbar candidates."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "A": {"ksampler": {spec.field_key: spec for spec in specs}}
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )


def field_spec(
    *,
    override_key: str,
    field_key: str,
    value: object,
    order: int,
    field_type: str,
    field_info: list[object] | None = None,
    presentation: FieldPresentation = FieldPresentation.STANDARD,
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
            presentation=presentation,
            override_behavior=OverrideBehavior(
                override_key=override_key,
                pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                toolbar_order=order,
            ),
        ),
    )


def show_settings_search(harness: ToolbarHarness) -> None:
    """Project the toolbar into settings route state."""

    harness.manager.mainwindow._active_workspace_route = SETTINGS_WORKSPACE_ROUTE
    harness.manager.clear_toolbar_override_controls()
    harness.parts.settings_toolbar_search_box.setVisible(True)
    harness.parts.pending_restart_button.set_collapsed(True)
    harness.parts.pending_restart_button.refresh_toolbar_spacing()
    harness.settle_layout()


def show_workflow_restart(harness: ToolbarHarness) -> None:
    """Project the toolbar into workflow state with restart advisory."""

    harness.manager.mainwindow._active_workspace_route = "workflow"
    harness.parts.settings_toolbar_search_box.hide()
    harness.parts.pending_restart_button.set_count(1)
    harness.parts.pending_restart_button.set_collapsed(False)
    harness.settle_layout()


def show_workflow_without_restart(harness: ToolbarHarness) -> None:
    """Project the toolbar into workflow state without restart advisory."""

    harness.manager.mainwindow._active_workspace_route = "workflow"
    harness.parts.settings_toolbar_search_box.hide()
    harness.parts.pending_restart_button.set_count(0)
    harness.parts.pending_restart_button.set_collapsed(True)
    harness.settle_layout()


def rebuild_real_overrides(harness: ToolbarHarness) -> tuple[QWidget, ...]:
    """Run the real override manager and return mounted widgets in order."""

    harness.manager.rebuild_active_override_controls()
    harness.settle_layout()
    ordered: list[QWidget] = []
    for key in ("sampler_name", "scheduler", "seed"):
        label, widget = harness.manager._global_override_controls[key]  # noqa: SLF001
        ordered.append(cast(QWidget, label))
        ordered.append(cast(QWidget, widget))
    return tuple(ordered)


def widget_gap(left: QWidget, right: QWidget) -> int:
    """Return the rendered horizontal gap between two toolbar widgets."""

    return right.geometry().x() - (left.geometry().x() + left.geometry().width())


def assert_natural_override_gaps(
    widgets: Sequence[QWidget],
    *,
    spacing: int,
) -> None:
    """Assert every real override pair uses only normal layout spacing."""

    gaps = [widget_gap(left, right) for left, right in zip(widgets, widgets[1:])]
    assert gaps == [spacing] * (len(widgets) - 1)


def seed_override_geometry(harness: ToolbarHarness) -> tuple[object, ...]:
    """Return complete visible geometry for the production seed pair."""

    rebuild_real_overrides(harness)
    label, control = harness.manager._global_override_controls["seed"]  # noqa: SLF001
    assert isinstance(label, CaptionLabel)
    assert isinstance(control, SeedBox)
    return (
        label.text(),
        label.isVisible(),
        label.geometry(),
        type(control),
        control.size(),
        control.sizeHint(),
        control.minimumSizeHint(),
        control.sizePolicy(),
        control.line_edit.geometry(),
        control.split_button.geometry(),
    )


__all__ = [
    "ToolbarHarness",
    "assert_natural_override_gaps",
    "field_spec",
    "override_snapshot",
    "rebuild_real_overrides",
    "render_manager_toolbar",
    "seed_override_geometry",
    "show_settings_search",
    "show_workflow_restart",
    "show_workflow_without_restart",
    "widget_gap",
]
