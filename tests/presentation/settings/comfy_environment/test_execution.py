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

"""Test Comfy environment plan execution and failure reporting."""

from __future__ import annotations

from typing import Any, cast


from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.presentation.settings.comfy_environment_page import (
    ComfyEnvironmentOperationFailure,
)
from tests.presentation.settings.comfy_environment.backend import EnvironmentBackend
from tests.presentation.settings.comfy_environment.backend_variants import (
    ApplyEnvironmentBackend,
)
from tests.presentation.settings.comfy_environment.support import (
    application,
    deliver_queued_events,
    environment_page,
)


def test_environment_page_apply_button_starts_plan_job_when_applyable() -> None:
    """Apply should request a backend job when the plan is applyable."""

    app = application()
    backend = ApplyEnvironmentBackend()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(backend),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)
    page.select_inventory_item("package:torch")
    page.update_package_button.click()
    deliver_queued_events(app)

    assert page.planned_changes_panel.apply_button.isEnabled()
    expected_revision = cast(Any, page)._maintenance_plan.revision

    page.planned_changes_panel.apply_button.click()
    deliver_queued_events(app)

    assert backend.applied_revisions == [expected_revision]
    job_text = page.job_label.text()
    assert job_text.startswith("Maintenance plan queued for execution.") or (
        job_text == "Waiting for Comfy to come back."
    )


def test_environment_page_reports_operation_failures_through_presenter() -> None:
    """Exception-backed environment operations should open the unified error modal."""

    application()
    presented: list[dict[str, Any]] = []
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: None,
        error_presenter=type(
            "_Presenter",
            (),
            {"show_exception_report": lambda _self, **kwargs: presented.append(kwargs)},
        )(),
    )
    failure = RuntimeError("plan failed")

    page._show_operation_failure(
        ComfyEnvironmentOperationFailure(
            operation="comfy_environment.plan.apply",
            title="Apply planned changes failed",
            message="Planned changes could not be applied.",
            error=failure,
            package_name="torch",
            values={"revision": 3},
        )
    )

    assert presented[0]["title"] == "Apply planned changes failed"
    assert presented[0]["stage"] == "settings"
    assert presented[0]["error"] is failure
    context = presented[0]["context"]
    assert context.operation == "comfy_environment.plan.apply"
    assert context.package_name == "torch"
    assert context.values["revision"] == 3
    page.close()
    page.deleteLater()
