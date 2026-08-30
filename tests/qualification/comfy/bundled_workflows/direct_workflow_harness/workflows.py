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

"""Load direct workflows and inspect their completed production projections."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from substitute.application.direct_workflows import DirectWorkflowLoadService
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.workflows.editor_projection_service import (
    DIRECT_WORKFLOW_SECTION_KEY,
)
from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)
from substitute.presentation.editor.panel.cube_section_build_plan import (
    NodeCardBuildOutcome,
)
from substitute.presentation.editor.panel.cube_section_build_session import (
    CubeSectionBuildSession,
)
from substitute.presentation.editor.panel.projection_coordinator import (
    EditorPanelProjectionCoordinator,
)
from substitute.presentation.editor.panel.widgets.cube_section import CubeSectionView
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.rendering import (
    rendered_node_names,
)


def load_direct_workflow(
    shell: DirectWorkflowShell,
    path: Path,
    *,
    node_definitions: Mapping[str, Mapping[str, object]],
    expected_node_names: frozenset[str],
) -> None:
    """Load a workflow and wait for its expected atomic card projection."""

    load_direct_workflow_and_wait(shell, path, node_definitions=node_definitions)
    panel = shell.shell.editor_panels[shell.direct_workflow_id]

    def expected_projection_visible() -> bool:
        """Return whether the completed projection exposes required card owners."""

        return expected_node_names.issubset(set(rendered_node_names(shell))) and not (
            panel.is_projection_active()
        )

    shell.wait_until(
        expected_projection_visible,
        description=f"direct workflow cards {sorted(expected_node_names)!r}",
    )


def load_direct_workflow_and_wait(
    shell: DirectWorkflowShell,
    path: Path,
    *,
    node_definitions: Mapping[str, Mapping[str, object]],
    timeout_ms: int = 30_000,
) -> None:
    """Load one workflow and wait for its complete production card projection."""

    shell.shell.node_definition_gateway.install_recorded_definitions(node_definitions)
    service = DirectWorkflowLoadService(
        ComfyWorkflowDocumentRepository(),
        node_definition_gateway=shell.shell.node_definition_gateway,
    )
    workflow = shell.shell.workflow_session_service.get_workflow(
        shell.direct_workflow_id
    )
    if workflow is None:
        raise AssertionError("direct workflow session disappeared")
    workflow.direct_workflow = service.load(path)
    shell.activate_direct(animated=True)
    shell.wait_for_transition()
    panel = shell.shell.editor_panels[shell.direct_workflow_id]

    def projection_complete() -> bool:
        """Finalize eligible reveals and report complete projection ownership."""

        if panel.has_pending_visible_projection_commit():
            panel.finalize_pending_visible_projection()
        shell.process_events()
        return not panel.is_projection_active()

    shell.wait_until(
        projection_complete,
        description=f"complete direct workflow projection for {path.name}",
        timeout_ms=timeout_ms,
    )


def direct_behavior_snapshot(shell: DirectWorkflowShell) -> EditorBehaviorSnapshot:
    """Return the behavior snapshot consumed by the direct projection."""

    panel = shell.shell.editor_panels[shell.direct_workflow_id]
    snapshot = panel.current_behavior_snapshot()
    if not isinstance(snapshot, EditorBehaviorSnapshot):
        raise AssertionError("direct workflow behavior snapshot is unavailable")
    return snapshot


def direct_node_card_build_outcomes(
    shell: DirectWorkflowShell,
) -> tuple[NodeCardBuildOutcome, ...]:
    """Return per-node outcomes retained by the direct build registry."""

    panel = shell.shell.editor_panels[shell.direct_workflow_id]
    coordinator = getattr(panel, "_projection_coordinator", None)
    if not isinstance(coordinator, EditorPanelProjectionCoordinator):
        raise AssertionError("direct workflow projection coordinator is unavailable")
    record = coordinator._composition.build_registry.record_for(  # noqa: SLF001
        DIRECT_WORKFLOW_SECTION_KEY
    )
    if record is None or record.state != "complete":
        raise AssertionError("direct workflow build record is not complete")
    session = record.session
    if not isinstance(session, CubeSectionBuildSession):
        raise AssertionError("direct workflow build session is unavailable")
    return session.node_outcomes


def direct_section_view(shell: DirectWorkflowShell) -> CubeSectionView:
    """Return the section that owns direct-workflow masonry layout."""

    panel = shell.shell.editor_panels[shell.direct_workflow_id]
    cube_widgets = cast(dict[str, object], getattr(cast(Any, panel), "cube_widgets"))
    section = cube_widgets.get(DIRECT_WORKFLOW_SECTION_KEY)
    if not isinstance(section, CubeSectionView):
        raise AssertionError("direct workflow section view is unavailable")
    return section
