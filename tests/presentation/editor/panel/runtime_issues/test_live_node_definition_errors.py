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

"""Tests for editor presentation of live Comfy metadata failures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QApplication

from substitute.application.node_behavior import (
    LiveNodeDefinitionError,
    MissingLiveNodeDefinition,
    NodeBehaviorService,
)
from substitute.application.ports import NodeDefinitionHydrationResult
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.panel.projection_runtime_issue_integration import (
    EditorProjectionRuntimeIssueIntegration,
    RuntimeIssueIntegrationPanelPort,
)
from tests.support.execution.runtime_support import (
    immediate_editor_panel_execution_factories,
)
from tests.support.localization import empty_node_presentation_service
from tests.support.qt.lifecycle import destroy_qt_object


class _EmptyNodeDefinitionGateway:
    """Return empty node definitions for editor-panel construction."""

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no live node definition data for the requested class."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return no required live node definition data for the requested class."""

        _ = node_class
        return {}


class _FailingHydrationService:
    """Raise a live definition error when projection hydration is requested."""

    def hydrate_for_projection(
        self,
        *,
        cube_states: Mapping[str, object],
        stack_order: Sequence[str],
    ) -> NodeDefinitionHydrationResult | None:
        """Raise the metadata failure used by the test."""

        _ = cube_states, stack_order
        raise LiveNodeDefinitionError(
            operation="hydrate editor projection node definitions",
            missing_definitions=(
                MissingLiveNodeDefinition(
                    class_type="SimpleSyrup.DetailSEGSByScaleFactor",
                    cube_aliases=("Automask Detailer",),
                    node_names=("detailer",),
                ),
            ),
        )


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication used by editor-panel tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_editor_hydration_error_can_register_cube_runtime_issue() -> None:
    """A cube-attributed missing live definition should register inline issue state."""

    _ensure_qapp()
    gateway = _EmptyNodeDefinitionGateway()
    panel = EditorPanel(
        node_definition_gateway=gateway,
        prompt_autocomplete_gateway=SimpleNamespace(),
        prompt_wildcard_catalog_gateway=SimpleNamespace(),
        node_behavior_service=NodeBehaviorService(node_definition_gateway=gateway),
        node_presentation_service=empty_node_presentation_service(),
        workflow_id="workflow-a",
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )
    panel_for_test = cast(Any, panel)
    reports: list[tuple[object, str]] = []
    panel_for_test._present_live_node_definition_error = lambda error, *, reason: (
        reports.append((error, reason))
    )
    panel_for_test._node_definition_hydration_service = _FailingHydrationService()
    panel_for_test._cube_states = {
        "Automask Detailer": SimpleNamespace(buffer={"nodes": {}})
    }
    panel_for_test._stack_order = ["Automask Detailer"]

    try:
        with pytest.raises(LiveNodeDefinitionError) as error_info:
            panel.hydrate_node_definitions_for_projection(reason="test_projection")
        handled = EditorProjectionRuntimeIssueIntegration(
            cast(RuntimeIssueIntegrationPanelPort, panel)
        ).register_recoverable_live_definition_error(
            error_info.value,
            reason="test_projection",
            workflow_id="workflow-a",
        )
        issues = panel.cube_runtime_issues("Automask Detailer")
        errored_aliases = panel.cube_runtime_error_aliases()
    finally:
        destroy_qt_object(panel)

    assert handled
    assert reports == []
    assert errored_aliases == ()
    assert issues[0].missing_node_classes == ("SimpleSyrup.DetailSEGSByScaleFactor",)


def test_unowned_live_node_definition_error_never_opens_error_report() -> None:
    """An unmatched missing class must not open an error modal."""

    _ensure_qapp()
    gateway = _EmptyNodeDefinitionGateway()
    panel = EditorPanel(
        node_definition_gateway=gateway,
        prompt_autocomplete_gateway=SimpleNamespace(),
        prompt_wildcard_catalog_gateway=SimpleNamespace(),
        node_behavior_service=NodeBehaviorService(node_definition_gateway=gateway),
        node_presentation_service=empty_node_presentation_service(),
        workflow_id="workflow-a",
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )
    error = LiveNodeDefinitionError(
        operation="resolve wrapper body node metadata",
        missing_definitions=(
            MissingLiveNodeDefinition(
                class_type="SimpleSyrup.KSamplerMixtureOfDiffusers",
                cube_aliases=(),
                node_names=("resize_by_factor",),
            ),
        ),
    )
    reports: list[tuple[object, str]] = []
    cast(Any, panel)._present_live_node_definition_error = lambda error, *, reason: (
        reports.append((error, reason))
    )

    try:
        handled = EditorProjectionRuntimeIssueIntegration(
            cast(RuntimeIssueIntegrationPanelPort, panel)
        ).register_recoverable_live_definition_error(
            error,
            reason="prompt_link_reconciliation",
            workflow_id="workflow-a",
        )
    finally:
        destroy_qt_object(panel)

    assert not handled
    assert reports == []
