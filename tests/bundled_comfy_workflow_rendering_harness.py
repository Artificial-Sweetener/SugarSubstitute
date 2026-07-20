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

import json
import logging
import traceback
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from types import TracebackType
from typing import Any, cast

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    ResolvedFieldSpec,
)
from substitute.application.workflows.editor_projection_service import (
    DIRECT_WORKFLOW_SECTION_KEY,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.presentation.editor.panel import node_card_builder
from substitute.presentation.editor.panel.behavior.behavior_applier import (
    EditorBehaviorApplier,
)
from substitute.presentation.editor.panel.cube_section_build_plan import (
    NodeCardBuildOutcome,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    LAYOUT_HANDLED,
)
from substitute.presentation.editor.panel.factories.field_build_outcome import (
    EditorFieldBuildKind,
)
from substitute.presentation.editor.panel.factories.field_build_resolver import (
    classify_editor_field_result,
)
from substitute.presentation.editor.panel.field_sync_controller import (
    EditorPanelFieldSyncController,
)
from substitute.presentation.editor.panel.rendering.render_transaction import (
    EditorRenderTransaction,
)
from tests.bundled_comfy_workflow_catalog import (
    BundledWorkflowCatalog,
    BundledWorkflowCatalogEntry,
    SourceWorkflowInventory,
    inventory_source_workflow,
    load_bundled_workflow_catalog,
    load_workflow_document,
)
from tests.real_shell_direct_workflow_harness import RealShellDirectWorkflowHarness


@dataclass(frozen=True, slots=True)
class AuditFinding:
    """Describe one observed production exception or lifecycle contradiction."""

    workflow: str
    category: str
    code: str
    stage: str
    message: str
    node_id: str = ""
    class_type: str = ""
    field_key: str = ""
    exception_type: str = ""
    traceback: str = ""


@dataclass(frozen=True, slots=True)
class FieldSpecObservation:
    """Persist one production-resolved field contract without interpreting it."""

    field_key: str
    field_type: str
    presentation: str
    control_name: str
    hidden: bool
    value_source: str
    value_type: str
    value_repr: str
    raw_value_type: str
    raw_value_repr: str
    constraints_repr: str
    meta_info_repr: str


@dataclass(frozen=True, slots=True)
class FieldFactoryObservation:
    """Persist one real call into the production field-factory pipeline."""

    node_id: str
    class_type: str
    field_key: str
    field_type: str
    presentation: str
    control_name: str
    value_source: str
    result: str
    widget_type: str
    exception_type: str
    exception_message: str
    traceback: str
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class RuntimeLogObservation:
    """Persist one warning-or-higher Python log record from a workflow load."""

    level: str
    logger: str
    message: str
    traceback: str


@dataclass(frozen=True, slots=True)
class CardVisibilityEvent:
    """Persist one production operation that set a card's visibility."""

    node_id: str
    event: str
    requested_visible: bool
    actual_visible: bool | None
    base_card_visible: bool | None


@dataclass(frozen=True, slots=True)
class CardLifecycleObservation:
    """Persist the final production card registry and masonry state for one node."""

    registered: bool
    widget_type: str
    valid: bool
    parent_type: str
    in_masonry: bool
    masonry_index: int | None
    visible: bool
    hidden: bool
    base_card_visible: bool | None
    has_title_controls: bool | None
    geometry: tuple[int, int, int, int] | None
    registered_field_keys: tuple[str, ...]
    visibility_events: tuple[CardVisibilityEvent, ...]


@dataclass(frozen=True, slots=True)
class NodeObservation:
    """Persist production-owned behavior, factories, outcome, and card state."""

    node_id: str
    class_type: str
    title: str
    behavior_present: bool
    decision_present: bool
    decision_visible: bool | None
    decision_enabled: bool | None
    decision_reason: str
    decision_show_enabled_switch: bool | None
    field_specs: tuple[FieldSpecObservation, ...]
    factory_observations: tuple[FieldFactoryObservation, ...]
    build_outcomes: tuple[NodeCardBuildOutcome, ...]
    card: CardLifecycleObservation


@dataclass(frozen=True, slots=True)
class WorkflowAuditResult:
    """Persist one workflow's complete passive production observation."""

    workflow: str
    title: str
    category: str
    source_node_count: int
    source_projected_node_count: int
    converted_node_count: int
    behavior_node_count: int
    build_outcome_count: int
    built_card_count: int
    final_visible_card_count: int
    registered_field_widget_count: int
    elapsed_ms: float
    screenshot: str
    nodes: tuple[NodeObservation, ...]
    runtime_logs: tuple[RuntimeLogObservation, ...]
    findings: tuple[AuditFinding, ...]

    @property
    def succeeded(self) -> bool:
        """Return whether no production failure was observed."""

        return not self.findings


@dataclass(frozen=True, slots=True)
class BundledWorkflowAuditReport:
    """Persist aggregate accounting for one complete observational corpus run."""

    schema_version: int
    audit_mode: str
    qt_platform: str
    template_root: str
    catalog_fingerprint: str
    workflow_count: int
    succeeded_workflow_count: int
    failed_workflow_count: int
    source_node_count: int
    source_projected_node_count: int
    converted_node_count: int
    build_outcome_count: int
    built_card_count: int
    final_visible_card_count: int
    registered_field_widget_count: int
    factory_observation_count: int
    factory_result_counts: Mapping[str, int]
    build_outcome_counts: Mapping[str, int]
    finding_count: int
    finding_counts_by_code: Mapping[str, int]
    elapsed_ms: float
    results: tuple[WorkflowAuditResult, ...]


class ProductionFieldFactoryObserver:
    """Wrap the production field entry point and preserve its real result."""

    def __init__(self) -> None:
        """Initialize an uninstalled observer with no recorded calls."""

        self._original: Callable[..., object] | None = None
        self._observations: list[FieldFactoryObservation] = []

    def __enter__(self) -> ProductionFieldFactoryObserver:
        """Install the passive wrapper around the builder module's imported entry."""

        if self._original is not None:
            raise RuntimeError("Production field observer is already installed.")
        original = cast(
            Callable[..., object],
            getattr(node_card_builder, "build_widget_for_field_spec"),
        )
        self._original = original

        def observed_build_widget_for_field_spec(
            *args: object,
            **kwargs: object,
        ) -> object:
            """Call production unchanged while recording its result or exception."""

            field_spec = kwargs.get("field_spec")
            if not isinstance(field_spec, ResolvedFieldSpec):
                return original(*args, **kwargs)
            started_at = perf_counter()
            try:
                result = original(*args, **kwargs)
            except Exception as error:
                self._observations.append(
                    self._observation(
                        field_spec,
                        result="exception",
                        elapsed_ms=(perf_counter() - started_at) * 1000.0,
                        exception=error,
                        traceback_text=traceback.format_exc(),
                    )
                )
                raise
            outcome = classify_editor_field_result(
                field_spec=field_spec,
                result=result,
                layout_handled_sentinel=LAYOUT_HANDLED,
            )
            result_name = outcome.kind.value
            if outcome.rendered:
                result_name = "widget_built"
                widget = result[0] if isinstance(result, tuple) else result
                widget_type = type(widget).__name__
            else:
                widget_type = ""
            self._observations.append(
                self._observation(
                    field_spec,
                    result=result_name,
                    widget_type=widget_type,
                    elapsed_ms=(perf_counter() - started_at) * 1000.0,
                )
            )
            return result

        setattr(
            node_card_builder,
            "build_widget_for_field_spec",
            observed_build_widget_for_field_spec,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Restore the exact production entry point after observation."""

        del exc_type, exc, tb
        original = self._original
        self._original = None
        if original is not None:
            setattr(node_card_builder, "build_widget_for_field_spec", original)

    def reset(self) -> None:
        """Discard observations from the previously completed workflow."""

        self._observations.clear()

    def observations(self) -> tuple[FieldFactoryObservation, ...]:
        """Return the calls recorded for the current workflow."""

        return tuple(self._observations)

    @staticmethod
    def _observation(
        field_spec: ResolvedFieldSpec,
        *,
        result: str,
        elapsed_ms: float,
        widget_type: str = "",
        exception: Exception | None = None,
        traceback_text: str = "",
    ) -> FieldFactoryObservation:
        """Build one immutable observation from a production field contract."""

        behavior = field_spec.field_behavior
        return FieldFactoryObservation(
            node_id=field_spec.node_name,
            class_type=field_spec.class_type,
            field_key=field_spec.field_key,
            field_type=field_spec.field_type or "",
            presentation=behavior.presentation.value,
            control_name=behavior.control_name or "",
            value_source=field_spec.value_source.value,
            result=result,
            widget_type=widget_type,
            exception_type=type(exception).__name__ if exception is not None else "",
            exception_message=str(exception) if exception is not None else "",
            traceback=traceback_text,
            elapsed_ms=elapsed_ms,
        )


class WorkflowRuntimeLogCapture(logging.Handler):
    """Capture warning-or-higher runtime logs for the active workflow."""

    def __init__(self) -> None:
        """Initialize a warning-level handler with an empty record buffer."""

        super().__init__(level=logging.WARNING)
        self._observations: list[RuntimeLogObservation] = []

    def reset(self) -> None:
        """Discard captured records from the previously completed workflow."""

        self._observations.clear()

    def observations(self) -> tuple[RuntimeLogObservation, ...]:
        """Return captured records for the current workflow."""

        return tuple(self._observations)

    def emit(self, record: logging.LogRecord) -> None:
        """Persist one log record without interfering with normal handlers."""

        try:
            trace = (
                "".join(traceback.format_exception(*record.exc_info))
                if record.exc_info is not None
                else ""
            )
            self._observations.append(
                RuntimeLogObservation(
                    level=record.levelname,
                    logger=record.name,
                    message=record.getMessage(),
                    traceback=trace,
                )
            )
        except Exception:
            self.handleError(record)


class ProductionCardVisibilityObserver:
    """Record production visibility mutations without recomputing their policy."""

    def __init__(self) -> None:
        """Initialize an uninstalled observer with no mutation events."""

        self._events: list[CardVisibilityEvent] = []
        self._original_behavior_visibility: Callable[..., object] | None = None
        self._original_empty_card_visibility: Callable[..., object] | None = None
        self._original_render_attach: Callable[..., object] | None = None

    def __enter__(self) -> ProductionCardVisibilityObserver:
        """Wrap the three production owners that directly reveal or hide cards."""

        if self._original_behavior_visibility is not None:
            raise RuntimeError("Production visibility observer is already installed.")
        behavior_visibility = cast(
            Callable[..., object],
            getattr(EditorBehaviorApplier, "_set_wrapper_visible"),
        )
        empty_card_visibility = cast(
            Callable[..., object],
            getattr(EditorPanelFieldSyncController, "_set_card_visible"),
        )
        render_attach = cast(
            Callable[..., object],
            getattr(EditorRenderTransaction, "attach_node_card"),
        )
        self._original_behavior_visibility = behavior_visibility
        self._original_empty_card_visibility = empty_card_visibility
        self._original_render_attach = render_attach

        def observe_behavior_visibility(
            owner: object,
            alias: str,
            node_name: str,
            visible: bool,
        ) -> object:
            """Record production behavior snapshot visibility application."""

            result = behavior_visibility(owner, alias, node_name, visible)
            if alias == DIRECT_WORKFLOW_SECTION_KEY:
                wrapper = _behavior_wrapper(owner, alias, node_name)
                self._events.append(
                    _visibility_event(
                        node_name=node_name,
                        event="behavior_snapshot",
                        requested_visible=visible,
                        wrapper=wrapper,
                    )
                )
            return result

        def observe_empty_card_visibility(
            owner: object,
            wrapper: object,
            visible: bool,
        ) -> object:
            """Record production empty-card reconciliation visibility."""

            result = empty_card_visibility(owner, wrapper, visible)
            cube_alias = _widget_property(wrapper, "cube_alias")
            node_name = _widget_property(wrapper, "node_name")
            if cube_alias == DIRECT_WORKFLOW_SECTION_KEY and isinstance(node_name, str):
                self._events.append(
                    _visibility_event(
                        node_name=node_name,
                        event="empty_card_reconciliation",
                        requested_visible=visible,
                        wrapper=wrapper,
                    )
                )
            return result

        def observe_render_attach(owner: object, card: object) -> object:
            """Record production render-transaction attachment reveals."""

            result = render_attach(owner, card)
            cube_alias = _widget_property(card, "cube_alias")
            node_name = _widget_property(card, "node_name")
            if cube_alias == DIRECT_WORKFLOW_SECTION_KEY and isinstance(node_name, str):
                self._events.append(
                    _visibility_event(
                        node_name=node_name,
                        event="render_transaction_attach",
                        requested_visible=True,
                        wrapper=card,
                    )
                )
            return result

        setattr(
            EditorBehaviorApplier,
            "_set_wrapper_visible",
            observe_behavior_visibility,
        )
        setattr(
            EditorPanelFieldSyncController,
            "_set_card_visible",
            observe_empty_card_visibility,
        )
        setattr(
            EditorRenderTransaction,
            "attach_node_card",
            observe_render_attach,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Restore the exact production visibility methods after observation."""

        del exc_type, exc, tb
        restorations = (
            (
                EditorBehaviorApplier,
                "_set_wrapper_visible",
                self._original_behavior_visibility,
            ),
            (
                EditorPanelFieldSyncController,
                "_set_card_visible",
                self._original_empty_card_visibility,
            ),
            (
                EditorRenderTransaction,
                "attach_node_card",
                self._original_render_attach,
            ),
        )
        self._original_behavior_visibility = None
        self._original_empty_card_visibility = None
        self._original_render_attach = None
        for owner, method_name, original in restorations:
            if original is not None:
                setattr(owner, method_name, original)

    def reset(self) -> None:
        """Discard visibility events from the previously completed workflow."""

        self._events.clear()

    def events(self) -> tuple[CardVisibilityEvent, ...]:
        """Return visibility operations recorded for the current workflow."""

        return tuple(self._events)


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
        self._shell: RealShellDirectWorkflowHarness | None = None
        self._field_observer = ProductionFieldFactoryObserver()
        self._visibility_observer = ProductionCardVisibilityObserver()
        self._log_capture = WorkflowRuntimeLogCapture()

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
        report = self._build_report(
            tuple(results),
            elapsed_ms=(perf_counter() - started_at) * 1000.0,
        )
        self.write_report(self._artifact_root / "report.json", report)
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
        shell = RealShellDirectWorkflowHarness()
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

    def _required_shell(self) -> RealShellDirectWorkflowHarness:
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
            shell.load_direct_workflow_and_wait(
                entry.path,
                node_definitions=self._node_definitions,
                timeout_ms=self._workflow_timeout_ms,
            )
            direct = self._direct_workflow_state(shell)
            converted_nodes = self._converted_nodes(direct)
            converted_node_count = len(converted_nodes)
            findings.extend(
                self._conversion_findings(entry, inventory, converted_nodes)
            )
            snapshot = shell.direct_behavior_snapshot()
            behavior_nodes = snapshot.resolved_nodes_by_alias.get(
                DIRECT_WORKFLOW_SECTION_KEY,
                {},
            )
            behavior_node_count = len(behavior_nodes)
            outcomes = shell.direct_node_card_build_outcomes()
            build_outcome_count = len(outcomes)
            panel = shell.shell.editor_panels[shell.direct_workflow_id]
            cards = self._card_map(
                cast(
                    Mapping[object, object], getattr(cast(Any, panel), "card_wrappers")
                )
            )
            fields = self._field_map(
                cast(
                    Mapping[object, object],
                    getattr(cast(Any, panel), "input_widgets_by_field_key"),
                )
            )
            section = shell.direct_section_view()
            section.finalize_layout_for_reveal(reason="bundled_workflow_observation")
            shell.process_events()
            masonry_order = section.node_card_order()
            built_card_count = len(cards)
            final_visible_card_count = sum(card.isVisible() for card in cards.values())
            registered_field_widget_count = len(fields)
            factory_observations = self._field_observer.observations()
            visibility_events = self._visibility_observer.events()
            nodes = self._node_observations(
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
                self._production_findings(
                    entry=entry,
                    nodes=nodes,
                    masonry_order=masonry_order,
                    cards=cards,
                )
            )
            findings.extend(self._masonry_findings(entry, cards))
            if findings:
                screenshot_path = self._screenshot_root / f"{entry.name}.png"
                if shell.shell.grab().save(str(screenshot_path)):
                    screenshot = str(screenshot_path)
        except Exception as error:
            findings.append(
                self._finding(
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

    @staticmethod
    def _direct_workflow_state(
        shell: RealShellDirectWorkflowHarness,
    ) -> DirectWorkflowState:
        """Return the direct document currently installed in production shell state."""

        workflow = shell.shell.workflow_session_service.get_workflow(
            shell.direct_workflow_id
        )
        direct = workflow.direct_workflow if workflow is not None else None
        if not isinstance(direct, DirectWorkflowState):
            raise AssertionError("direct workflow state is unavailable after loading")
        return direct

    @staticmethod
    def _converted_nodes(
        direct: DirectWorkflowState,
    ) -> dict[str, Mapping[str, object]]:
        """Return typed converted nodes from one direct workflow buffer."""

        raw_nodes = direct.buffer.get("nodes")
        if not isinstance(raw_nodes, Mapping):
            raise AssertionError("converted direct workflow has no node mapping")
        return {
            str(node_id): node
            for node_id, node in raw_nodes.items()
            if isinstance(node, Mapping)
        }

    def _conversion_findings(
        self,
        entry: BundledWorkflowCatalogEntry,
        inventory: SourceWorkflowInventory,
        converted_nodes: Mapping[str, Mapping[str, object]],
    ) -> tuple[AuditFinding, ...]:
        """Report only source-to-production conversion identity contradictions."""

        expected = {node.node_id: node for node in inventory.projected_nodes}
        findings: list[AuditFinding] = []
        for node_id in sorted(set(expected) - set(converted_nodes)):
            findings.append(
                self._finding(
                    entry,
                    code="conversion_missing_node",
                    stage="conversion",
                    message="A source-projectable node is absent after conversion.",
                    node_id=node_id,
                    class_type=expected[node_id].class_type,
                )
            )
        for node_id in sorted(set(converted_nodes) - set(expected)):
            findings.append(
                self._finding(
                    entry,
                    code="conversion_unexpected_node",
                    stage="conversion",
                    message="Conversion produced a node absent from source expansion.",
                    node_id=node_id,
                    class_type=str(converted_nodes[node_id].get("class_type", "")),
                )
            )
        for node_id in sorted(set(expected) & set(converted_nodes)):
            actual_class = str(converted_nodes[node_id].get("class_type", ""))
            if actual_class != expected[node_id].class_type:
                findings.append(
                    self._finding(
                        entry,
                        code="conversion_class_mismatch",
                        stage="conversion",
                        message=(
                            f"Source class {expected[node_id].class_type!r} became "
                            f"{actual_class!r}."
                        ),
                        node_id=node_id,
                        class_type=actual_class,
                    )
                )
        return tuple(findings)

    def _node_observations(
        self,
        *,
        converted_nodes: Mapping[str, Mapping[str, object]],
        snapshot: EditorBehaviorSnapshot,
        outcomes: tuple[NodeCardBuildOutcome, ...],
        cards: Mapping[str, QWidget],
        fields: Mapping[tuple[str, str], QWidget],
        masonry_order: tuple[str, ...],
        factory_observations: tuple[FieldFactoryObservation, ...],
        visibility_events: tuple[CardVisibilityEvent, ...],
    ) -> tuple[NodeObservation, ...]:
        """Assemble production evidence for every converted node identity."""

        behaviors = snapshot.resolved_nodes_by_alias.get(
            DIRECT_WORKFLOW_SECTION_KEY,
            {},
        )
        decisions = snapshot.card_decisions_by_alias.get(
            DIRECT_WORKFLOW_SECTION_KEY,
            {},
        )
        specs_by_node = snapshot.field_specs_by_alias.get(
            DIRECT_WORKFLOW_SECTION_KEY,
            {},
        )
        outcomes_by_node: dict[str, list[NodeCardBuildOutcome]] = {}
        for outcome in outcomes:
            outcomes_by_node.setdefault(outcome.node_name, []).append(outcome)
        factories_by_node: dict[str, list[FieldFactoryObservation]] = {}
        for observation in factory_observations:
            factories_by_node.setdefault(observation.node_id, []).append(observation)
        visibility_by_node: dict[str, list[CardVisibilityEvent]] = {}
        for event in visibility_events:
            visibility_by_node.setdefault(event.node_id, []).append(event)
        masonry_indices = {
            node_id: index for index, node_id in enumerate(masonry_order)
        }
        observations: list[NodeObservation] = []
        for node_id, node_data in converted_nodes.items():
            class_type = str(node_data.get("class_type", ""))
            meta = node_data.get("_meta")
            title = str(meta.get("title", "")) if isinstance(meta, Mapping) else ""
            decision = decisions.get(node_id)
            observations.append(
                NodeObservation(
                    node_id=node_id,
                    class_type=class_type,
                    title=title,
                    behavior_present=node_id in behaviors,
                    decision_present=decision is not None,
                    decision_visible=(
                        bool(decision.visible) if decision is not None else None
                    ),
                    decision_enabled=(
                        bool(decision.enabled) if decision is not None else None
                    ),
                    decision_reason=(
                        str(decision.reason) if decision is not None else ""
                    ),
                    decision_show_enabled_switch=(
                        bool(decision.show_enabled_switch)
                        if decision is not None
                        else None
                    ),
                    field_specs=tuple(
                        self._field_spec_observation(spec)
                        for spec in specs_by_node.get(node_id, {}).values()
                    ),
                    factory_observations=tuple(factories_by_node.get(node_id, ())),
                    build_outcomes=tuple(outcomes_by_node.get(node_id, ())),
                    card=self._card_observation(
                        node_id=node_id,
                        card=cards.get(node_id),
                        fields=fields,
                        masonry_index=masonry_indices.get(node_id),
                        visibility_events=tuple(visibility_by_node.get(node_id, ())),
                    ),
                )
            )
        return tuple(observations)

    @staticmethod
    def _field_spec_observation(spec: ResolvedFieldSpec) -> FieldSpecObservation:
        """Convert one resolved field contract into prompt-safe persisted evidence."""

        behavior = spec.field_behavior
        return FieldSpecObservation(
            field_key=spec.field_key,
            field_type=spec.field_type or "",
            presentation=behavior.presentation.value,
            control_name=behavior.control_name or "",
            hidden=behavior.hidden,
            value_source=spec.value_source.value,
            value_type=type(spec.value).__name__,
            value_repr=_safe_repr(spec.value),
            raw_value_type=type(spec.raw_value).__name__,
            raw_value_repr=_safe_repr(spec.raw_value),
            constraints_repr=_safe_repr(spec.constraints),
            meta_info_repr=_safe_repr(_redacted_mapping(spec.meta_info)),
        )

    @staticmethod
    def _card_observation(
        *,
        node_id: str,
        card: QWidget | None,
        fields: Mapping[tuple[str, str], QWidget],
        masonry_index: int | None,
        visibility_events: tuple[CardVisibilityEvent, ...],
    ) -> CardLifecycleObservation:
        """Read final registry, attachment, visibility, geometry, and field state."""

        field_keys = tuple(
            sorted(
                field_key for field_node, field_key in fields if field_node == node_id
            )
        )
        if card is None:
            return CardLifecycleObservation(
                registered=False,
                widget_type="",
                valid=False,
                parent_type="",
                in_masonry=masonry_index is not None,
                masonry_index=masonry_index,
                visible=False,
                hidden=True,
                base_card_visible=None,
                has_title_controls=None,
                geometry=None,
                registered_field_keys=field_keys,
                visibility_events=visibility_events,
            )
        valid = bool(isValid(card))
        parent = card.parentWidget() if valid else None
        geometry = (
            cast(tuple[int, int, int, int], card.geometry().getRect())
            if valid
            else None
        )
        return CardLifecycleObservation(
            registered=True,
            widget_type=type(card).__name__,
            valid=valid,
            parent_type=type(parent).__name__ if parent is not None else "",
            in_masonry=masonry_index is not None,
            masonry_index=masonry_index,
            visible=card.isVisible() if valid else False,
            hidden=card.isHidden() if valid else True,
            base_card_visible=_optional_bool_property(card, "base_card_visible"),
            has_title_controls=_optional_bool_property(card, "has_title_controls"),
            geometry=geometry,
            registered_field_keys=field_keys,
            visibility_events=visibility_events,
        )

    def _production_findings(
        self,
        *,
        entry: BundledWorkflowCatalogEntry,
        nodes: tuple[NodeObservation, ...],
        masonry_order: tuple[str, ...],
        cards: Mapping[str, QWidget],
    ) -> tuple[AuditFinding, ...]:
        """Report exceptions and contradictions in observed production operations."""

        findings: list[AuditFinding] = []
        converted_ids = {node.node_id for node in nodes}
        for node in nodes:
            if not node.behavior_present:
                findings.append(
                    self._finding(
                        entry,
                        code="missing_production_behavior",
                        stage="behavior",
                        message="Converted node has no production behavior.",
                        node_id=node.node_id,
                        class_type=node.class_type,
                    )
                )
            if len(node.build_outcomes) != 1:
                findings.append(
                    self._finding(
                        entry,
                        code="build_outcome_cardinality",
                        stage="card_build",
                        message=(
                            "Converted node received "
                            f"{len(node.build_outcomes)} production build outcomes."
                        ),
                        node_id=node.node_id,
                        class_type=node.class_type,
                    )
                )
            factory_exception = False
            for observation in node.factory_observations:
                if observation.result == EditorFieldBuildKind.UNSUPPORTED.value:
                    findings.append(
                        self._finding(
                            entry,
                            code="field_factory_unhandled",
                            stage="field_factory",
                            message=(
                                "The production field-factory pipeline has no "
                                "registered editor for this field."
                            ),
                            node_id=node.node_id,
                            class_type=node.class_type,
                            field_key=observation.field_key,
                        )
                    )
                elif observation.result == "exception":
                    factory_exception = True
                    findings.append(
                        self._finding(
                            entry,
                            code="field_factory_exception",
                            stage="field_factory",
                            message=observation.exception_message,
                            node_id=node.node_id,
                            class_type=node.class_type,
                            field_key=observation.field_key,
                            exception_type=observation.exception_type,
                            traceback_text=observation.traceback,
                        )
                    )
            if len(node.build_outcomes) != 1:
                continue
            outcome = node.build_outcomes[0]
            if outcome.kind == "build_error" and not factory_exception:
                findings.append(
                    self._finding(
                        entry,
                        code="node_card_build_exception",
                        stage="card_build",
                        message=outcome.message
                        or "Production card construction failed.",
                        node_id=node.node_id,
                        class_type=node.class_type,
                    )
                )
            if outcome.kind == "built":
                if not node.card.registered:
                    findings.append(
                        self._finding(
                            entry,
                            code="built_card_missing_registry",
                            stage="card_registry",
                            message="Production reported built but registered no card.",
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
                elif not node.card.valid:
                    findings.append(
                        self._finding(
                            entry,
                            code="built_card_invalid_qt_object",
                            stage="card_lifecycle",
                            message="Registered production card is no longer a valid Qt object.",
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
                if not node.card.in_masonry:
                    findings.append(
                        self._finding(
                            entry,
                            code="built_card_missing_masonry",
                            stage="masonry",
                            message="Built card is absent from production masonry order.",
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
            else:
                if node.card.registered:
                    findings.append(
                        self._finding(
                            entry,
                            code="unbuilt_node_registered_card",
                            stage="card_registry",
                            message=(
                                f"Production outcome {outcome.kind!r} retained a card."
                            ),
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
                if node.card.registered_field_keys:
                    findings.append(
                        self._finding(
                            entry,
                            code="unbuilt_node_retained_field_widgets",
                            stage="card_cleanup",
                            message=(
                                f"Production outcome {outcome.kind!r} retained fields: "
                                f"{', '.join(node.card.registered_field_keys)}."
                            ),
                            node_id=node.node_id,
                            class_type=node.class_type,
                        )
                    )
        unexpected_masonry = set(masonry_order) - converted_ids
        unexpected_registry = set(cards) - converted_ids
        for node_id in sorted(unexpected_masonry | unexpected_registry):
            findings.append(
                self._finding(
                    entry,
                    code="stale_or_unexpected_card",
                    stage="card_lifecycle",
                    message="Card state contains a node absent from this converted workflow.",
                    node_id=node_id,
                )
            )
        return tuple(findings)

    def _masonry_findings(
        self,
        entry: BundledWorkflowCatalogEntry,
        cards: Mapping[str, QWidget],
    ) -> tuple[AuditFinding, ...]:
        """Report invalid final geometry for cards production left visible."""

        findings: list[AuditFinding] = []
        visible_cards = [
            (node_id, card)
            for node_id, card in cards.items()
            if isValid(card) and card.isVisible()
        ]
        for node_id, card in visible_cards:
            geometry = card.geometry()
            parent = card.parentWidget()
            if geometry.width() <= 0 or geometry.height() <= 0:
                findings.append(
                    self._geometry_finding(
                        entry,
                        node_id,
                        card,
                        code="visible_card_empty_geometry",
                        message="Visible production card has empty geometry.",
                    )
                )
            if geometry.x() < 0 or geometry.y() < 0:
                findings.append(
                    self._geometry_finding(
                        entry,
                        node_id,
                        card,
                        code="visible_card_negative_position",
                        message="Visible production card starts outside masonry bounds.",
                    )
                )
            if parent is None or not parent.rect().contains(geometry):
                findings.append(
                    self._geometry_finding(
                        entry,
                        node_id,
                        card,
                        code="visible_card_out_of_bounds",
                        message="Visible production card extends beyond its parent.",
                    )
                )
        for index, (left_id, left_card) in enumerate(visible_cards):
            for right_id, right_card in visible_cards[index + 1 :]:
                if _positive_intersection(left_card.geometry(), right_card.geometry()):
                    findings.append(
                        self._finding(
                            entry,
                            code="visible_cards_overlap",
                            stage="masonry",
                            message=f"Visible cards {left_id!r} and {right_id!r} overlap.",
                            node_id=f"{left_id},{right_id}",
                        )
                    )
        return tuple(findings)

    def _geometry_finding(
        self,
        entry: BundledWorkflowCatalogEntry,
        node_id: str,
        card: QWidget,
        *,
        code: str,
        message: str,
    ) -> AuditFinding:
        """Build one card-geometry finding with observed node context."""

        return self._finding(
            entry,
            code=code,
            stage="masonry",
            message=f"{message} Geometry={card.geometry().getRect()!r}",
            node_id=node_id,
            class_type=str(card.property("node_class_type") or ""),
        )

    @staticmethod
    def _card_map(raw_cards: Mapping[object, object]) -> dict[str, QWidget]:
        """Return direct-section registered cards indexed by production identity."""

        cards: dict[str, QWidget] = {}
        for key, card in raw_cards.items():
            if (
                isinstance(key, tuple)
                and len(key) == 2
                and key[0] == DIRECT_WORKFLOW_SECTION_KEY
                and isinstance(key[1], str)
                and isinstance(card, QWidget)
            ):
                cards[key[1]] = card
        return cards

    @staticmethod
    def _field_map(
        raw_fields: Mapping[object, object],
    ) -> dict[tuple[str, str], QWidget]:
        """Return direct-section registered fields indexed by production identity."""

        fields: dict[tuple[str, str], QWidget] = {}
        for key, widget in raw_fields.items():
            if (
                isinstance(key, tuple)
                and len(key) == 3
                and key[0] == DIRECT_WORKFLOW_SECTION_KEY
                and isinstance(key[1], str)
                and isinstance(key[2], str)
                and isinstance(widget, QWidget)
            ):
                fields[(key[1], key[2])] = widget
        return fields

    @staticmethod
    def _finding(
        entry: BundledWorkflowCatalogEntry,
        *,
        code: str,
        stage: str,
        message: str,
        node_id: str = "",
        class_type: str = "",
        field_key: str = "",
        exception_type: str = "",
        traceback_text: str = "",
    ) -> AuditFinding:
        """Build one workflow-scoped observed failure record."""

        return AuditFinding(
            workflow=entry.name,
            category=entry.category,
            code=code,
            stage=stage,
            message=message,
            node_id=node_id,
            class_type=class_type,
            field_key=field_key,
            exception_type=exception_type,
            traceback=traceback_text,
        )

    def _build_report(
        self,
        results: tuple[WorkflowAuditResult, ...],
        *,
        elapsed_ms: float,
    ) -> BundledWorkflowAuditReport:
        """Aggregate accounting without reclassifying production outcomes."""

        findings = [finding for result in results for finding in result.findings]
        factory_observations = [
            observation
            for result in results
            for node in result.nodes
            for observation in node.factory_observations
        ]
        build_outcomes = [
            outcome
            for result in results
            for node in result.nodes
            for outcome in node.build_outcomes
        ]
        app = QApplication.instance()
        qt_platform = app.platformName() if isinstance(app, QApplication) else ""
        return BundledWorkflowAuditReport(
            schema_version=1,
            audit_mode="passive_production_observation",
            qt_platform=qt_platform,
            template_root=str(self._catalog.template_root),
            catalog_fingerprint=self._catalog.fingerprint,
            workflow_count=len(results),
            succeeded_workflow_count=sum(result.succeeded for result in results),
            failed_workflow_count=sum(not result.succeeded for result in results),
            source_node_count=sum(result.source_node_count for result in results),
            source_projected_node_count=sum(
                result.source_projected_node_count for result in results
            ),
            converted_node_count=sum(result.converted_node_count for result in results),
            build_outcome_count=sum(result.build_outcome_count for result in results),
            built_card_count=sum(result.built_card_count for result in results),
            final_visible_card_count=sum(
                result.final_visible_card_count for result in results
            ),
            registered_field_widget_count=sum(
                result.registered_field_widget_count for result in results
            ),
            factory_observation_count=len(factory_observations),
            factory_result_counts=dict(
                sorted(Counter(item.result for item in factory_observations).items())
            ),
            build_outcome_counts=dict(
                sorted(Counter(item.kind for item in build_outcomes).items())
            ),
            finding_count=len(findings),
            finding_counts_by_code=dict(
                sorted(Counter(item.code for item in findings).items())
            ),
            elapsed_ms=elapsed_ms,
            results=results,
        )

    @staticmethod
    def write_report(path: Path, report: BundledWorkflowAuditReport) -> None:
        """Persist one complete observational JSON report."""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(report), indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _optional_bool_property(widget: QWidget, property_name: str) -> bool | None:
    """Return a bool-valued Qt property without interpreting absent state."""

    value = widget.property(property_name)
    return value if isinstance(value, bool) else None


def _behavior_wrapper(owner: object, alias: str, node_name: str) -> object | None:
    """Return the wrapper addressed by production behavior-application ports."""

    ports = getattr(owner, "_ports", None)
    card_wrapper = getattr(ports, "card_wrapper", None)
    if not callable(card_wrapper):
        return None
    try:
        return cast(object | None, card_wrapper(alias, node_name))
    except (RuntimeError, TypeError):
        return None


def _widget_property(widget: object | None, property_name: str) -> object:
    """Read one Qt dynamic property from an observed production widget."""

    getter = getattr(widget, "property", None)
    if not callable(getter):
        return None
    try:
        return getter(property_name)
    except (RuntimeError, TypeError):
        return None


def _visibility_event(
    *,
    node_name: str,
    event: str,
    requested_visible: bool,
    wrapper: object | None,
) -> CardVisibilityEvent:
    """Build one visibility event from the production operation's final state."""

    is_visible = getattr(wrapper, "isVisible", None)
    try:
        actual_visible = bool(is_visible()) if callable(is_visible) else None
    except RuntimeError:
        actual_visible = None
    base_visible = _widget_property(wrapper, "base_card_visible")
    return CardVisibilityEvent(
        node_id=node_name,
        event=event,
        requested_visible=bool(requested_visible),
        actual_visible=actual_visible,
        base_card_visible=(base_visible if isinstance(base_visible, bool) else None),
    )


def _positive_intersection(left: QRect, right: QRect) -> bool:
    """Return whether two final card geometries overlap with positive area."""

    intersection = left.intersected(right)
    return intersection.width() > 0 and intersection.height() > 0


def _safe_repr(value: object, *, limit: int = 2000) -> str:
    """Return a bounded diagnostic representation without raising."""

    try:
        rendered = repr(value)
    except Exception as error:
        rendered = f"<repr failed: {type(error).__name__}: {error}>"
    return rendered if len(rendered) <= limit else f"{rendered[:limit]}…"


def _redacted_mapping(value: Mapping[str, object]) -> dict[str, object]:
    """Redact secret-shaped metadata keys before diagnostic persistence."""

    redacted: dict[str, object] = {}
    for key, item in value.items():
        normalized = str(key).casefold()
        if any(
            term in normalized for term in ("token", "secret", "password", "api_key")
        ):
            redacted[str(key)] = "<redacted>"
        else:
            redacted[str(key)] = item
    return redacted


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
