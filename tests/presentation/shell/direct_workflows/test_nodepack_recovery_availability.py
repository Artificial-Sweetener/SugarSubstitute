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

"""Exercise recovery offers when the connected Comfy session is not managed."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlan,
    WorkflowNodepackRecoveryPlanService,
)
from substitute.infrastructure.comfy.workflow_nodepack_installer import (
    WorkflowNodepackInstaller,
    WorkflowNodepackInstallResult,
)
from substitute.presentation.shell.direct_workflow_nodepack_recovery import (
    DirectWorkflowNodepackRecoveryController,
)
from substitute.presentation.shell.workflow_nodepack_recovery_execution import (
    WorkflowNodepackRecoveryRoute,
)
from tests.support.execution import ImmediateTaskSubmitter
from tests.support.nodepack_recovery import Handoff, Installer, Plans, plan


def test_external_comfy_session_does_not_offer_automatic_install(
    tmp_path: Path,
) -> None:
    """Do not install into a workspace whose Comfy process we cannot restart."""

    reviews: list[WorkflowNodepackRecoveryPlan] = []
    installer = Installer(WorkflowNodepackInstallResult(items=()))
    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(
            WorkflowNodepackRecoveryPlanService, Plans([plan(missing=True)])
        ),
        installer=cast(WorkflowNodepackInstaller, installer),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        present_review=lambda plan, _approve, _cancel: reviews.append(plan),
        present_failure=lambda _id, _stage, _error: None,
        can_restart=lambda: False,
        handoff_provider=lambda: Handoff(),
        request_restart=lambda: True,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.recover(workflow={"nodes": [], "links": []}, target_workflow_id="wf")

    assert reviews == []
    assert installer.calls == []
