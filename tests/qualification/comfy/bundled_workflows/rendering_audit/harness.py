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

"""Observe bundled workflows through the unmodified production editor path."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable, Mapping
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from PySide6.QtWidgets import QApplication

from substitute.application.workflows.editor_projection_service import (
    DIRECT_WORKFLOW_SECTION_KEY,
)
from tests.qualification.comfy.bundled_workflows.catalog import (
    BundledWorkflowCatalog,
    BundledWorkflowCatalogEntry,
    inventory_source_workflow,
    load_bundled_workflow_catalog,
    load_workflow_document,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.workflows import (
    direct_behavior_snapshot,
    direct_node_card_build_outcomes,
    direct_section_view,
    load_direct_workflow_and_wait,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.models import (
    AuditFinding,
    BundledWorkflowAuditReport,
    CardLifecycleObservation,
    CardVisibilityEvent,
    FieldFactoryObservation,
    FieldSpecObservation,
    NodeObservation,
    RuntimeLogObservation,
    WorkflowAuditResult,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.finding_audit import (
    FindingAuditor,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.field_factory import (
    ProductionFieldFactoryObserver,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.card_visibility import (
    ProductionCardVisibilityObserver,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.card_registry import (
    card_map,
    field_map,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.conversion_audit import (
    converted_nodes as converted_nodes_from_state,
    conversion_findings,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.runtime_logs import (
    WorkflowRuntimeLogCapture,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.node_observation import (
    NodeObservationCollector,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.workflow_state import (
    direct_workflow_state,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.reporting import (
    build_report,
    write_report,
)


class BundledComfyWorkflowRenderingHarness:
    """Passively audit official templates through production direct projection."""

    def __init__(
        self,
        *,
        template_root: Path,
        node_definitions: Mapping[str, Mapping[str, object]],
        artifact_root: Path,
        shell_batch_size: int = 25,
        workflow_timeout_ms: int = 30_000,
        progress_callback: Callable[[int, int, WorkflowAuditResult], None]
        | None = None,
    ) -> None:
        """Store deterministic corpus, metadata, artifact, and isolation inputs."""

        if shell_batch_size < 1:
            raise ValueError("Shell batch size must be positive.")
        if workflow_timeout_ms < 1:
            raise ValueError("Workflow timeout must be positive.")
        self._catalog = load_bundled_workflow_catalog(template_root)
        self._node_definitions = node_definitions
        self._artifact_root = artifact_root.resolve()
        self._screenshot_root = self._artifact_root / "screenshots"
        self._shell_batch_size = shell_batch_size
        self._workflow_timeout_ms = workflow_timeout_ms
        self._progress_callback = progress_callback
        self._shell: DirectWorkflowShell | None = None
        self._field_observer = ProductionFieldFactoryObserver()
        self._visibility_observer = ProductionCardVisibilityObserver()
        self._log_capture = WorkflowRuntimeLogCapture()
        self._node_observer = NodeObservationCollector()
        self._finding_auditor = FindingAuditor()

    @property
    def catalog(self) -> BundledWorkflowCatalog:
        """Return the authoritative catalog selected for this run."""

        return self._catalog

    def run(self) -> BundledWorkflowAuditReport:
        """Audit every catalog workflow and continue after contained failures."""

        self._assert_offscreen_platform()
        started_at = perf_counter()
        results: list[WorkflowAuditResult] = []
        self._artifact_root.mkdir(parents=True, exist_ok=True)
        self._screenshot_root.mkdir(parents=True, exist_ok=True)
        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_capture)
        try:
            with self._field_observer, self._visibility_observer:
                for index, entry in enumerate(self._catalog.entries):
                    if index % self._shell_batch_size == 0:
                        self._replace_shell()
                    result = self._audit_entry(entry)
                    results.append(result)
                    if self._progress_callback is not None:
                        self._progress_callback(
                            index + 1,
                            len(self._catalog.entries),
                            result,
                        )
        finally:
            root_logger.removeHandler(self._log_capture)
            self._close_shell()
        app = QApplication.instance()
        report = build_report(
            self._catalog,
            tuple(results),
            qt_platform=app.platformName() if isinstance(app, QApplication) else "",
            elapsed_ms=(perf_counter() - started_at) * 1000.0,
        )
        write_report(self._artifact_root / "report.json", report)
        return report

    def run_probe(self, workflow_name: str) -> WorkflowAuditResult:
        """Audit one named workflow after proving the active Qt backend is offscreen."""

        self._assert_offscreen_platform()
        entry = next(
            (item for item in self._catalog.entries if item.name == workflow_name),
            None,
        )
        if entry is None:
            raise ValueError(f"Bundled workflow is not in index.json: {workflow_name}")
        self._artifact_root.mkdir(parents=True, exist_ok=True)
        self._screenshot_root.mkdir(parents=True, exist_ok=True)
        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_capture)
        try:
            with self._field_observer, self._visibility_observer:
                self._replace_shell()
                result = self._audit_entry(entry)
        finally:
            root_logger.removeHandler(self._log_capture)
            self._close_shell()
        return result

    @staticmethod
    def _assert_offscreen_platform() -> None:
        """Fail closed unless Qt is already running on the offscreen backend."""

        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError("The production audit requires an active QApplication.")
        platform = app.platformName().casefold()
        if platform != "offscreen":
            raise RuntimeError(
                f"Refusing production audit on interactive Qt platform {platform!r}."
            )

    def _replace_shell(self) -> None:
        """Replace the production shell at a deterministic corpus batch boundary."""

        self._close_shell()
        shell = DirectWorkflowShell(self._artifact_root / "shell")
        shell.shell.resize(2200, 1000)
        shell.shell.splitter.setSizes([1500, 700])
        shell.process_events()
        self._shell = shell

    def _close_shell(self) -> None:
        """Close the current production shell when one is active."""

        shell = self._shell
        self._shell = None
        if shell is not None:
            shell.close()

    def _required_shell(self) -> DirectWorkflowShell:
        """Return the current shell or fail when batch setup did not run."""

        if self._shell is None:
            raise RuntimeError("Bundled workflow audit shell is unavailable.")
        return self._shell

    def _audit_entry(self, entry: BundledWorkflowCatalogEntry) -> WorkflowAuditResult:
        """Observe one workflow while containing its production exceptions."""

        started_at = perf_counter()
        self._field_observer.reset()
        self._visibility_observer.reset()
        self._log_capture.reset()
        findings: list[AuditFinding] = []
        nodes: tuple[NodeObservation, ...] = ()
        source_node_count = 0
        source_projected_node_count = 0
        converted_node_count = 0
        behavior_node_count = 0
        build_outcome_count = 0
        built_card_count = 0
        final_visible_card_count = 0
        registered_field_widget_count = 0
        screenshot = ""
        try:
            workflow = load_workflow_document(entry.path)
            inventory = inventory_source_workflow(workflow)
            source_node_count = len(inventory.nodes)
            source_projected_node_count = len(inventory.projected_nodes)
            shell = self._required_shell()
            load_direct_workflow_and_wait(
                shell,
                entry.path,
                node_definitions=self._node_definitions,
                timeout_ms=self._workflow_timeout_ms,
            )
            direct = direct_workflow_state(shell)
            converted_nodes = converted_nodes_from_state(direct)
            converted_node_count = len(converted_nodes)
            findings.extend(conversion_findings(entry, inventory, converted_nodes))
            snapshot = direct_behavior_snapshot(shell)
            behavior_nodes = snapshot.resolved_nodes_by_alias.get(
                DIRECT_WORKFLOW_SECTION_KEY,
                {},
            )
            behavior_node_count = len(behavior_nodes)
            outcomes = direct_node_card_build_outcomes(shell)
            build_outcome_count = len(outcomes)
            panel = shell.shell.editor_panels[shell.direct_workflow_id]
            cards = card_map(
                cast(
                    Mapping[object, object], getattr(cast(Any, panel), "card_wrappers")
                )
            )
            fields = field_map(
                cast(
                    Mapping[object, object],
                    getattr(cast(Any, panel), "input_widgets_by_field_key"),
                )
            )
            section = direct_section_view(shell)
            section.finalize_layout_for_reveal(reason="bundled_workflow_observation")
            shell.process_events()
            masonry_order = section.node_card_order()
            built_card_count = len(cards)
            final_visible_card_count = sum(card.isVisible() for card in cards.values())
            registered_field_widget_count = len(fields)
            factory_observations = self._field_observer.observations()
            visibility_events = self._visibility_observer.events()
            nodes = self._node_observer.collect(
                converted_nodes=converted_nodes,
                snapshot=snapshot,
                outcomes=outcomes,
                cards=cards,
                fields=fields,
                masonry_order=masonry_order,
                factory_observations=factory_observations,
                visibility_events=visibility_events,
            )
            findings.extend(
                self._finding_auditor.production_findings(
                    entry=entry,
                    nodes=nodes,
                    masonry_order=masonry_order,
                    cards=cards,
                )
            )
            findings.extend(self._finding_auditor.masonry_findings(entry, cards))
            if findings:
                screenshot_path = self._screenshot_root / f"{entry.name}.png"
                if shell.shell.grab().save(str(screenshot_path)):
                    screenshot = str(screenshot_path)
        except Exception as error:
            findings.append(
                self._finding_auditor.finding(
                    entry,
                    code="workflow_observation_exception",
                    stage="workflow",
                    message=str(error),
                    exception_type=type(error).__name__,
                    traceback_text=traceback.format_exc(),
                )
            )
            self._replace_shell()
        return WorkflowAuditResult(
            workflow=entry.name,
            title=entry.title,
            category=entry.category,
            source_node_count=source_node_count,
            source_projected_node_count=source_projected_node_count,
            converted_node_count=converted_node_count,
            behavior_node_count=behavior_node_count,
            build_outcome_count=build_outcome_count,
            built_card_count=built_card_count,
            final_visible_card_count=final_visible_card_count,
            registered_field_widget_count=registered_field_widget_count,
            elapsed_ms=(perf_counter() - started_at) * 1000.0,
            screenshot=screenshot,
            nodes=nodes,
            runtime_logs=self._log_capture.observations(),
            findings=tuple(findings),
        )


__all__ = [
    "AuditFinding",
    "BundledComfyWorkflowRenderingHarness",
    "BundledWorkflowAuditReport",
    "CardLifecycleObservation",
    "CardVisibilityEvent",
    "FieldFactoryObservation",
    "FieldSpecObservation",
    "NodeObservation",
    "ProductionFieldFactoryObserver",
    "ProductionCardVisibilityObserver",
    "RuntimeLogObservation",
    "WorkflowAuditResult",
]
