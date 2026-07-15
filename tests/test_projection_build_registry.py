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

"""Focused tests for pure cube-section build registry behavior."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.presentation.editor.panel.projection_build_registry import (
    CubeSectionBuildRegistry,
)
from tests.editor_projection_test_helpers import _Widget


def test_build_registry_refuses_reuse_when_definition_identity_changes() -> None:
    """Widget reuse should be gated by the rendered cube definition identity."""

    registry = CubeSectionBuildRegistry()
    widget = _Widget()
    registry.adopt_complete(
        alias="Demo",
        widget=widget,
        snapshot_identity=None,
        definition_identity=(
            "Demo",
            "Owner/Repo/demo.cube",
            "1.0",
            "sha256:old",
            "old-ref",
            "surface-old",
            "nodes-old",
        ),
    )

    assert not registry.can_reuse(
        "Demo",
        widget,
        (
            "Demo",
            "Owner/Repo/demo.cube",
            "2.0",
            "sha256:new",
            "new-ref",
            "surface-new",
            "nodes-new",
        ),
    )


def test_build_registry_reuse_decision_adopts_untracked_complete_widget() -> None:
    """Reuse decisions should adopt legacy visible widgets as complete records."""

    registry = CubeSectionBuildRegistry()
    widget = _Widget()
    identity = (
        "Demo",
        "Owner/Repo/demo.cube",
        "1.0",
        "sha256:demo",
        "ref-demo",
        "surface-demo",
        "nodes-demo",
    )

    decision = registry.reuse_decision("Demo", widget, identity)

    assert decision.can_reuse
    assert decision.record_present
    assert decision.record_state == "complete"
    assert decision.active_token is None
    assert decision.definition_identity == identity
    record = registry.record_for("Demo")
    assert record is not None
    assert record.widget is widget
    assert record.state == "complete"


def test_build_registry_reuse_decision_rejects_noncomplete_or_mismatched_records() -> (
    None
):
    """Reuse decisions should reject active, stale, cancelled, failed, or mismatched records."""

    identity = (
        "Demo",
        "Owner/Repo/demo.cube",
        "1.0",
        "sha256:demo",
        "ref-demo",
        "surface-demo",
        "nodes-demo",
    )
    replacement_identity = (
        "Demo",
        "Owner/Repo/demo.cube",
        "2.0",
        "sha256:replacement",
        "ref-replacement",
        "surface-replacement",
        "nodes-replacement",
    )

    building_registry = CubeSectionBuildRegistry()
    building_widget = _Widget("building")
    building_token = building_registry.start(
        alias="Demo",
        widget=building_widget,
        session=object(),
        snapshot_identity=None,
        definition_identity=identity,
    )
    building_decision = building_registry.reuse_decision(
        "Demo",
        building_widget,
        identity,
    )
    assert not building_decision.can_reuse
    assert building_decision.record_state == "building"
    assert building_decision.active_token is building_token

    stale_registry = CubeSectionBuildRegistry()
    stale_widget = _Widget("stale")
    stale_token = stale_registry.start(
        alias="Demo",
        widget=stale_widget,
        session=object(),
        snapshot_identity=None,
        definition_identity=identity,
    )
    stale_registry.mark_stale("Demo", "definition_changed")
    stale_decision = stale_registry.reuse_decision("Demo", stale_widget, identity)
    assert not stale_decision.can_reuse
    assert stale_decision.record_state == "stale"
    assert stale_decision.active_token is None
    stale_record = stale_registry.record_for("Demo")
    assert stale_record is not None
    assert stale_record.token is stale_token

    cancelled_registry = CubeSectionBuildRegistry()
    cancelled_widget = _Widget("cancelled")
    cancelled_token = cancelled_registry.start(
        alias="Demo",
        widget=cancelled_widget,
        session=object(),
        snapshot_identity=None,
        definition_identity=identity,
    )
    cancelled_registry.cancel("Demo", cancelled_token, "superseded")
    cancelled_decision = cancelled_registry.reuse_decision(
        "Demo",
        cancelled_widget,
        identity,
    )
    assert not cancelled_decision.can_reuse
    assert cancelled_decision.record_state == "cancelled"

    failed_registry = CubeSectionBuildRegistry()
    failed_widget = _Widget("failed")
    failed_token = failed_registry.start(
        alias="Demo",
        widget=failed_widget,
        session=object(),
        snapshot_identity=None,
        definition_identity=identity,
    )
    failed_registry.mark_failed("Demo", failed_token, RuntimeError("boom"))
    failed_decision = failed_registry.reuse_decision("Demo", failed_widget, identity)
    assert not failed_decision.can_reuse
    assert failed_decision.record_state == "failed"

    mismatch_registry = CubeSectionBuildRegistry()
    mismatch_widget = _Widget("mismatch")
    mismatch_registry.adopt_complete(
        alias="Demo",
        widget=mismatch_widget,
        snapshot_identity=None,
        definition_identity=identity,
    )
    mismatch_decision = mismatch_registry.reuse_decision(
        "Demo",
        mismatch_widget,
        replacement_identity,
    )
    assert not mismatch_decision.can_reuse
    assert mismatch_decision.record_state == "complete"
    assert mismatch_decision.active_token is None


def test_build_registry_mark_stale_reports_active_token_once() -> None:
    """Stale marking should expose an active token before transitioning to stale."""

    registry = CubeSectionBuildRegistry()
    token = registry.start(
        alias="Demo",
        widget=_Widget(),
        session=object(),
        snapshot_identity=None,
        definition_identity=None,
    )

    first_result = registry.mark_stale("Demo", "definition_changed")
    second_result = registry.mark_stale("Demo", "definition_changed_again")

    assert first_result.record_present
    assert first_result.was_building
    assert first_result.active_token is token
    assert first_result.state == "stale"
    assert second_result.record_present
    assert not second_result.was_building
    assert second_result.active_token is None
    assert second_result.state == "stale"


def test_build_registry_mark_complete_does_not_complete_stale_or_cancelled_record() -> (
    None
):
    """Completion should only apply while the caller still owns a building record."""

    stale_registry = CubeSectionBuildRegistry()
    stale_token = stale_registry.start(
        alias="Demo",
        widget=_Widget("stale"),
        session=object(),
        snapshot_identity=None,
        definition_identity=None,
    )
    stale_registry.mark_stale("Demo", "definition_changed")

    cancelled_registry = CubeSectionBuildRegistry()
    cancelled_token = cancelled_registry.start(
        alias="Demo",
        widget=_Widget("cancelled"),
        session=object(),
        snapshot_identity=None,
        definition_identity=None,
    )
    cancelled_registry.cancel("Demo", cancelled_token, "superseded")

    assert not stale_registry.mark_complete("Demo", stale_token)
    stale_record = stale_registry.record_for("Demo")
    assert stale_record is not None
    assert stale_record.state == "stale"
    assert not cancelled_registry.mark_complete("Demo", cancelled_token)
    cancelled_record = cancelled_registry.record_for("Demo")
    assert cancelled_record is not None
    assert cancelled_record.state == "cancelled"


def test_build_registry_cancel_preserves_failed_state() -> None:
    """Cancellation should not overwrite a recorded build failure."""

    registry = CubeSectionBuildRegistry()
    token = registry.start(
        alias="Demo",
        widget=_Widget(),
        session=object(),
        snapshot_identity=None,
        definition_identity=None,
    )

    assert registry.mark_failed("Demo", token, RuntimeError("boom"))
    assert not registry.cancel("Demo", token, "workflow_cancelled")
    record = registry.record_for("Demo")
    assert record is not None
    assert record.state == "failed"
    assert record.failure == "RuntimeError('boom')"


def test_projection_build_registry_remains_qt_free() -> None:
    """Pure registry state must not import Qt or concrete panel widgets."""

    module_path = Path(
        "substitute/presentation/editor/panel/projection_build_registry.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden_import_roots = {
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
    }
    forbidden_import_parts = {
        "widgets",
        "node_card",
    }

    for node in ast.walk(tree):
        imported_name = ""
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_name = alias.name
                assert imported_name.split(".")[0] not in forbidden_import_roots
                assert not any(
                    part in imported_name.split(".") for part in forbidden_import_parts
                )
        elif isinstance(node, ast.ImportFrom):
            imported_name = node.module or ""
            assert imported_name.split(".")[0] not in forbidden_import_roots
            assert not any(
                part in imported_name.split(".") for part in forbidden_import_parts
            )
