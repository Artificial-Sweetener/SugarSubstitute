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

"""Render and verify exact workflow nodepack recovery against two Comfy runtimes."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from hashlib import sha256
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped]  # noqa: E402

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (  # noqa: E402
    WorkflowNodepackResolutionService,
)
from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (  # noqa: E402
    WorkflowNodeDefinitionAssessmentService,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (  # noqa: E402
    WorkflowNodepackRecoveryPlan,
    WorkflowNodepackRecoveryPlanService,
)
from substitute.application.direct_workflows import DirectWorkflowLoadService  # noqa: E402
from substitute.application.generation.native_cube_workflow_builder import (  # noqa: E402
    NativeCubeWorkflowBuilder,
)
from substitute.domain.comfy_workflow import DirectWorkflowState  # noqa: E402
from substitute.domain.comfy_workflow.node_inventory import (  # noqa: E402
    workflow_node_inventory,
)
from substitute.domain.onboarding import ComfyEndpoint  # noqa: E402
from substitute.domain.workflow import WorkflowState  # noqa: E402
from substitute.infrastructure.comfy.comfy_workflow_nodepack_catalog import (  # noqa: E402
    ComfyWorkflowNodepackCatalog,
)
from substitute.infrastructure.comfy.workflow_document_repository import (  # noqa: E402
    ComfyWorkflowDocumentRepository,
)
from substitute.infrastructure.external.comfy_object_info_client import (  # noqa: E402
    ComfyObjectInfoClient,
)
from substitute.infrastructure.external.sugarcubes_workflow_analysis_client import (  # noqa: E402
    SugarCubesWorkflowAnalysisClient,
)
from substitute.presentation.dialogs.workflow_nodepack_recovery_dialog import (  # noqa: E402
    WorkflowNodepackRecoveryDialog,
)
from tools.editor_panel_baseline.rendering import (  # noqa: E402
    register_headless_fluent_font,
)
from tools.editor_projection_rig.qt_harness import (  # noqa: E402
    drain_qt_events,
    drain_until,
    ensure_qapplication,
)
from tools.workflow_nodepack_recovery_editor_evidence import (  # noqa: E402
    render_editor,
)

_HOST_SIZE = (1440, 1000)
_BACKGROUND = QColor("#202020")


def main() -> int:
    """Run qualification and return a process status suitable for automation."""

    arguments = _parse_arguments()
    evidence = qualify(
        workflow_path=arguments.workflow,
        before_port=arguments.before_port,
        after_port=arguments.after_port,
        recovery_workspace=arguments.recovery_workspace,
        output_dir=arguments.output_dir,
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


def qualify(
    *,
    workflow_path: Path,
    before_port: int,
    after_port: int,
    recovery_workspace: Path,
    output_dir: Path,
) -> dict[str, object]:
    """Prove degraded presentation, review, restart hydration, and graph readiness."""

    output_dir.mkdir(parents=True, exist_ok=True)
    application = ensure_qapplication()
    application.setProperty("substitute.reduce_motion", True)
    register_headless_fluent_font()
    application.setFont(QFont("Segoe UI", 10))
    setTheme(Theme.DARK)
    drain_qt_events(5)

    before_gateway, before_document = _load_document(workflow_path, before_port)
    before_plan = _plan(before_gateway, before_document)
    if not before_plan.assessment.missing:
        raise RuntimeError("Before-recovery Comfy has no missing workflow nodes.")
    if before_plan.resolution.unresolved:
        classes = ", ".join(
            item.node.class_type for item in before_plan.resolution.unresolved
        )
        raise RuntimeError(f"Recovery plan contains unresolved node classes: {classes}")

    review_path = output_dir / "recovery-review.png"
    _render_review(application, before_plan, review_path)
    before_editor = render_editor(
        workflow_id="nodepack-recovery-before",
        document=before_document,
        definitions=_available_definitions(before_gateway, before_document),
        path=output_dir / "degraded-editor.png",
    )
    expected_missing = sorted(
        node.class_type for node in before_plan.assessment.missing
    )
    rendered_missing = before_editor.get("degraded_definition_classes")
    if (
        not isinstance(rendered_missing, list)
        or sorted(rendered_missing) != expected_missing
    ):
        raise RuntimeError(
            "The degraded editor did not account for every missing workflow node."
        )

    after_gateway, after_document = _load_document(workflow_path, after_port)
    after_plan = _plan(after_gateway, after_document)
    if after_plan.assessment.missing:
        raise RuntimeError(
            "Recovered Comfy still lacks: "
            + ", ".join(after_plan.assessment.missing_class_types)
        )
    after_editor = render_editor(
        workflow_id="nodepack-recovery-after",
        document=after_document,
        definitions=_available_definitions(after_gateway, after_document),
        path=output_dir / "hydrated-editor.png",
    )
    if after_editor["degraded_card_count"]:
        raise RuntimeError("Recovered editor still contains degraded node cards.")

    graph = _build_native_graph(after_document)
    graph_classes = tuple(
        sorted({item.class_type for item in workflow_node_inventory(graph)})
    )
    hydration = after_gateway.ensure_node_definitions(graph_classes)
    if hydration.unavailable:
        raise RuntimeError(
            "Recovered execution graph still lacks: " + ", ".join(hydration.unavailable)
        )
    if "SafeMaskToImage" in json.dumps(graph, sort_keys=True):
        raise RuntimeError("Private legacy SafeMaskToImage remains in execution graph.")

    packages = tuple(_package_evidence(before_plan, recovery_workspace))
    evidence: dict[str, object] = {
        "schema_version": 1,
        "headless": application.platformName() == "offscreen",
        "workflow_path": str(workflow_path.resolve()),
        "workflow_sha256": _sha256(workflow_path),
        "before_port": before_port,
        "after_port": after_port,
        "missing_before": list(before_plan.assessment.missing_class_types),
        "missing_after": list(after_plan.assessment.missing_class_types),
        "packages": list(packages),
        "legacy_alias_removed": "SafeMaskToImage" not in json.dumps(graph),
        "core_replacement_present": "MaskToImage" in json.dumps(graph),
        "execution_class_count": len(graph_classes),
        "execution_classes_unavailable": list(hydration.unavailable),
        "before_editor": before_editor,
        "after_editor": after_editor,
        "renders": {
            "review": _render_evidence(review_path),
            "degraded_editor": _editor_render_evidence(before_editor),
            "hydrated_editor": _editor_render_evidence(after_editor),
        },
        "passed": True,
    }
    evidence_path = output_dir / "evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def _load_document(
    workflow_path: Path,
    port: int,
) -> tuple[ComfyObjectInfoClient, DirectWorkflowState]:
    """Load the exact document through production adapters for one Comfy runtime."""

    endpoint = ComfyEndpoint(host="127.0.0.1", port=port)
    gateway = ComfyObjectInfoClient(
        endpoint=endpoint,
        background_scheduler=lambda work: work(),
    )
    repository = ComfyWorkflowDocumentRepository()
    service = DirectWorkflowLoadService(
        repository,
        SugarCubesWorkflowAnalysisClient(endpoint),
        node_definition_gateway=gateway,
    )
    return gateway, service.load(workflow_path)


def _plan(
    gateway: ComfyObjectInfoClient,
    document: DirectWorkflowState,
) -> WorkflowNodepackRecoveryPlan:
    """Build the production Registry-first recovery plan for one document."""

    return WorkflowNodepackRecoveryPlanService(
        assessment=WorkflowNodeDefinitionAssessmentService(gateway),
        resolution=WorkflowNodepackResolutionService(ComfyWorkflowNodepackCatalog()),
    ).plan(document.source_workflow)


def _available_definitions(
    gateway: ComfyObjectInfoClient,
    document: DirectWorkflowState,
) -> dict[str, Mapping[str, object]]:
    """Return every live definition available for the document inventory."""

    definitions: dict[str, Mapping[str, object]] = {}
    classes = {
        item.class_type for item in workflow_node_inventory(document.source_workflow)
    }
    for class_type in sorted(classes):
        payload = gateway.get_required_node_definition(class_type)
        definition = payload.get(class_type)
        if isinstance(definition, Mapping):
            definitions[class_type] = definition
    return definitions


def _render_review(
    application: QApplication,
    plan: WorkflowNodepackRecoveryPlan,
    path: Path,
) -> None:
    """Render the production non-blocking review over its real full-window host."""

    host = QWidget()
    host.resize(*_HOST_SIZE)
    host.setStyleSheet("background: #202020;")
    host.show()
    dialog = WorkflowNodepackRecoveryDialog(plan, parent=host)
    try:
        dialog.open()
        drain_until(lambda: dialog.graphicsEffect() is None, max_turns=25)
        application.processEvents()
        if not dialog.isVisible() or not dialog.widget.isVisible():
            raise RuntimeError("Recovery review did not become visible for rendering.")
        _save_widget(host, path)
    finally:
        dialog.reject()
        host.close()
        host.deleteLater()
        drain_qt_events(20)


def _build_native_graph(document: DirectWorkflowState) -> dict[str, object]:
    """Build the exact post-recovery graph through production Cube materialization."""

    workflow = WorkflowState(direct_workflow=document)
    return NativeCubeWorkflowBuilder().build(
        workflow,
        enabled_node_keys_by_alias={},
        disabled_node_keys_by_alias={},
    )


def _package_evidence(
    plan: WorkflowNodepackRecoveryPlan,
    workspace: Path,
) -> list[dict[str, object]]:
    """Verify that every planned package is present in the recovery workspace."""

    packages: list[dict[str, object]] = []
    for candidate in plan.resolution.candidates:
        nodepack = candidate.nodepack
        folder_name = (
            nodepack.identifier
            if nodepack.repository_url is None
            else nodepack.repository_url.rstrip("/").rsplit("/", 1)[-1]
        ).removesuffix(".git")
        folder = workspace / "custom_nodes" / folder_name
        if not folder.is_dir():
            raise RuntimeError(f"Recovered package folder is absent: {folder_name}")
        git_head = _git_head(folder) if (folder / ".git").exists() else None
        if git_head is not None and git_head != nodepack.version:
            raise RuntimeError(
                f"Recovered Git package {folder_name} is not at its approved revision."
            )
        packages.append(
            {
                "identifier": nodepack.identifier,
                "source_kind": nodepack.source_kind.value,
                "version": nodepack.version,
                "class_types": list(candidate.class_types),
                "folder": str(folder.resolve()),
                "git_head": git_head,
            }
        )
    return packages


def _git_head(repository: Path) -> str:
    """Return the exact Git HEAD without invoking a shell."""

    import subprocess

    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _save_widget(widget: QWidget, path: Path) -> None:
    """Render one opaque widget surface to a PNG."""

    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(_BACKGROUND)
    painter = QPainter(image)
    widget.render(painter, QPoint())
    painter.end()
    if not image.save(str(path), "PNG"):  # type: ignore[call-overload]
        raise OSError(f"Could not save qualification render: {path}")


def _render_evidence(path: Path) -> dict[str, object]:
    """Return stable file evidence for one completed render."""

    image = QImage(str(path))
    sampled_colors = {
        image.pixel(x, y)
        for y in range(0, image.height(), 12)
        for x in range(0, image.width(), 12)
    }
    if len(sampled_colors) < 8:
        raise RuntimeError(f"Qualification render has no visible content: {path}")
    return {
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "width": image.width(),
        "height": image.height(),
        "sampled_color_count": len(sampled_colors),
    }


def _editor_render_evidence(
    editor_evidence: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    """Return verified image evidence for each editor viewport position."""

    raw_paths = editor_evidence.get("render_paths")
    if not isinstance(raw_paths, Mapping):
        raise RuntimeError("Editor qualification did not report render paths.")
    return {
        str(position): _render_evidence(Path(path))
        for position, path in raw_paths.items()
        if isinstance(path, str)
    }


def _sha256(path: Path) -> str:
    """Hash one evidence file without retaining its contents."""

    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_arguments() -> argparse.Namespace:
    """Parse exact workflow, endpoint, and evidence locations."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", type=Path)
    parser.add_argument("--before-port", type=int, default=8188)
    parser.add_argument("--after-port", type=int, default=8197)
    parser.add_argument("--recovery-workspace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
