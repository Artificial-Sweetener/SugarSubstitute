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

from substitute.application.errors import SubstituteOperationContext
from substitute.application.node_behavior import (
    LiveNodeDefinitionError,
    MissingLiveNodeDefinition,
    NodeBehaviorService,
)
from substitute.application.workflows import CubeRuntimeIssueSource
from substitute.application.ports import NodeDefinitionHydrationResult
from substitute.presentation.editor.panel.view import EditorPanel
from tests.execution_test_helpers import immediate_editor_panel_execution_factories
from tests.localization_testing import empty_node_presentation_service


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


class _RecordingErrorPresenter:
    """Record structured error reports requested by the editor panel."""

    def __init__(self) -> None:
        """Initialize the recorded call list."""

        self.comfy_reports: list[dict[str, object]] = []

    def show_error_report(self, report: object) -> None:
        """Record a prepared report when a caller uses the generic surface."""

        self.comfy_reports.append({"report": report})

    def show_exception_report(
        self,
        *,
        title: str,
        message: str,
        stage: str,
        error: BaseException,
        context: SubstituteOperationContext,
    ) -> None:
        """Record an exception report when a caller uses the exception surface."""

        self.comfy_reports.append(
            {
                "title": title,
                "message": message,
                "stage": stage,
                "error": error,
                "context": context,
            }
        )

    def show_comfy_connection_report(
        self,
        *,
        title: str,
        message: str,
        stage: str,
        context: SubstituteOperationContext,
        error: BaseException | None = None,
    ) -> None:
        """Record the Comfy metadata report shown by the editor panel."""

        self.comfy_reports.append(
            {
                "title": title,
                "message": message,
                "stage": stage,
                "error": error,
                "context": context,
            }
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
    presenter = _RecordingErrorPresenter()
    panel = EditorPanel(
        node_definition_gateway=gateway,
        prompt_autocomplete_gateway=SimpleNamespace(),
        prompt_wildcard_catalog_gateway=SimpleNamespace(),
        node_behavior_service=NodeBehaviorService(node_definition_gateway=gateway),
        node_presentation_service=empty_node_presentation_service(),
        error_presenter=presenter,
        workflow_id="workflow-a",
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )
    panel_for_test = cast(Any, panel)
    panel_for_test._node_definition_hydration_service = _FailingHydrationService()
    panel_for_test._cube_states = {
        "Automask Detailer": SimpleNamespace(buffer={"nodes": {}})
    }
    panel_for_test._stack_order = ["Automask Detailer"]

    try:
        with pytest.raises(LiveNodeDefinitionError) as error_info:
            panel.hydrate_node_definitions_for_projection(reason="test_projection")
        handled = panel.register_projection_live_node_definition_error(
            error_info.value,
            reason="test_projection",
            source=CubeRuntimeIssueSource.PROJECTION,
        )
        panel.present_recoverable_live_node_definition_error(
            error_info.value,
            reason="test_projection",
        )
        issues = panel.cube_runtime_issues("Automask Detailer")
        errored_aliases = panel.cube_runtime_error_aliases()
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()

    assert handled
    assert len(presenter.comfy_reports) == 1
    report = presenter.comfy_reports[0]
    assert report["title"] == "Live Comfy node definitions unavailable"
    assert report["error"] is error_info.value
    context = cast(SubstituteOperationContext, report["context"])
    assert context.operation == "hydrate editor projection node definitions"
    assert context.workflow_id == "workflow-a"
    assert context.values["projection_reason"] == "test_projection"
    assert context.values["missing_node_classes"] == (
        "SimpleSyrup.DetailSEGSByScaleFactor",
    )
    assert context.values["cube_aliases"] == ("Automask Detailer",)
    assert context.values["node_names"] == ("detailer",)
    assert errored_aliases == ("Automask Detailer",)
    assert issues[0].missing_node_classes == ("SimpleSyrup.DetailSEGSByScaleFactor",)


def test_recoverable_live_node_definition_report_is_deduplicated() -> None:
    """Recoverable live metadata reports should dedupe within one projection."""

    _ensure_qapp()
    gateway = _EmptyNodeDefinitionGateway()
    presenter = _RecordingErrorPresenter()
    panel = EditorPanel(
        node_definition_gateway=gateway,
        prompt_autocomplete_gateway=SimpleNamespace(),
        prompt_wildcard_catalog_gateway=SimpleNamespace(),
        node_behavior_service=NodeBehaviorService(node_definition_gateway=gateway),
        node_presentation_service=empty_node_presentation_service(),
        error_presenter=presenter,
        workflow_id="workflow-a",
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )
    error = LiveNodeDefinitionError(
        operation="resolve wrapper body node metadata",
        missing_definitions=(
            MissingLiveNodeDefinition(
                class_type="SimpleSyrup.KSamplerMixtureOfDiffusers",
                cube_aliases=("Anima/Diffusion Upscale",),
                node_names=("resize_by_factor",),
            ),
        ),
    )

    try:
        panel.present_recoverable_live_node_definition_error(
            error,
            reason="prompt_link_reconciliation",
        )
        panel.present_recoverable_live_node_definition_error(
            error,
            reason="prompt_link_reconciliation",
        )
        panel.begin_live_node_definition_report_projection()
        panel.present_recoverable_live_node_definition_error(
            error,
            reason="prompt_link_reconciliation",
        )
    finally:
        panel.deleteLater()
        _ensure_qapp().processEvents()

    assert len(presenter.comfy_reports) == 2
    assert presenter.comfy_reports[0]["error"] is error
    assert presenter.comfy_reports[1]["error"] is error
