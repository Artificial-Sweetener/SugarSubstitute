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

"""Verify honest setup progress and structured failure reporting."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from substitute.application.errors import ErrorReport
from substitute.application.onboarding import OnboardingProvisioningFailure
from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupProgressUnit,
    SetupTaskId,
    SetupTaskState,
)
from substitute.presentation.onboarding.onboarding_completion_pages import (
    ProvisioningPage,
)
from substitute.presentation.onboarding.onboarding_failure_presenter import (
    OnboardingFailurePresenter,
)
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.onboarding_window import OnboardingWindow
from substitute.presentation.onboarding.setup_progress_presenter import (
    SetupProgressPresenter,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from tests.support.qt.lifecycle import ensure_qt_application
from .controller_double import _FakeController


class _ReportPresenter:
    """Capture the shared structured error report boundary."""

    def __init__(self) -> None:
        """Initialize an empty report collection."""

        self.reports: list[ErrorReport] = []

    def show_error_report(self, report: ErrorReport) -> None:
        """Retain one report instead of opening a modal."""

        self.reports.append(report)


def test_progress_uses_exact_tasks_bytes_and_rejects_stale_generation() -> None:
    """Project only real completed work and exact model transfer bytes."""

    ensure_qt_application()
    page = ProvisioningPage()
    presenter = SetupProgressPresenter(page)
    presenter.begin()

    assert page.details_container.isHidden()
    assert page.activity_progress_bar.isHidden()
    assert presenter.accept(
        SetupProgressEvent(
            2,
            SetupTaskId.RUNTIME,
            SetupTaskState.COMPLETED,
            "Runtime ready",
        )
    )
    assert presenter.accept(
        SetupProgressEvent(
            2,
            SetupTaskId.MODEL_DOWNLOAD,
            SetupTaskState.RUNNING,
            "Downloading model",
            SetupProgressUnit.BYTES,
            25,
            100,
            "model.safetensors",
            current_item_index=2,
            total_items=3,
        )
    )
    assert not presenter.accept(
        SetupProgressEvent(
            1,
            SetupTaskId.COMMIT,
            SetupTaskState.COMPLETED,
            "stale",
        )
    )
    assert presenter.accept(
        SetupProgressEvent(
            2,
            SetupTaskId.RUNTIME,
            SetupTaskState.RUNNING,
            "late runtime event",
        )
    )
    assert presenter.accept(
        SetupProgressEvent(
            2,
            SetupTaskId.MODEL_DOWNLOAD,
            SetupTaskState.RUNNING,
            "late model event",
            SetupProgressUnit.BYTES,
            10,
            100,
            "model.safetensors",
        )
    )

    snapshot = presenter.snapshot()
    assert snapshot.completed_tasks == 1
    assert snapshot.total_tasks == 6
    assert snapshot.model_completed_bytes == 25
    assert snapshot.model_total_bytes == 100
    assert page.overall_progress_bar.value() == 17
    assert page.model_progress_bar.value() == 25
    assert "2 of 3" in page.model_progress_label.text()
    assert page.status_label.text() == "late model event"
    assert page.activity_progress_bar.isHidden() is False

    assert presenter.accept(
        SetupProgressEvent(
            2,
            SetupTaskId.MODEL_DOWNLOAD,
            SetupTaskState.COMPLETED,
            "Model download complete",
            SetupProgressUnit.BYTES,
            100,
            100,
            "model.safetensors",
            current_item_index=3,
            total_items=3,
        )
    )
    assert presenter.snapshot().model_complete
    assert "Downloading" not in page.model_progress_label.text()
    assert page.model_progress_bar.value() == 100
    page.close()


def test_failure_freezes_progress_and_reveals_inline_log() -> None:
    """Reveal diagnostic detail in the stable page when setup fails."""

    ensure_qt_application()
    page = ProvisioningPage()
    page.begin_progress()
    page.append_log("technical line")

    page.mark_failed()

    assert not page.details_container.isHidden()
    assert page.show_log_button.isChecked()
    assert "technical line" in page.details_surface.log_view.toPlainText()
    page.close()


def test_failure_presenter_redacts_paths_and_carries_recovery_context(
    tmp_path: Path,
) -> None:
    """Send a sanitized copyable report through the shared error presenter."""

    report_presenter = _ReportPresenter()
    presenter = OnboardingFailurePresenter(
        report_presenter=cast(ErrorReportPresenterProtocol, report_presenter),
        installation_root=tmp_path,
    )
    failure = OnboardingProvisioningFailure(
        headline="Setup needs attention",
        user_message="Fix the model transfer and try again.",
        technical_detail=f"download failed under {tmp_path}",
        remediation_steps=("Add a CivitAI API key.", "Try again."),
        transaction_id="transaction-123",
        failed_task="model_download",
    )

    presenter.present(failure, log_tail=f"request failed in {tmp_path}")

    assert len(report_presenter.reports) == 1
    report = report_presenter.reports[0]
    assert report.runtime.launch_args == ()
    assert report.operation_context is not None
    assert report.operation_context.trace_id == "transaction-123"
    assert report.operation_context.values["failed_task"] == "model_download"
    assert report.technical_detail is not None
    assert str(tmp_path) not in report.technical_detail
    assert "Add a CivitAI API key" in report.technical_detail
    assert "Setup log tail" in report.technical_detail


def test_visible_completion_and_failure_request_attention_once_each(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Deduplicate terminal attention without stealing focus in the window owner."""

    ensure_qt_application()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    controller = _FakeController(draft, OnboardingFlowMode.FIRST_RUN)
    reports = _ReportPresenter()
    attention: list[object] = []

    def request_attention(owner: object) -> bool:
        """Record the narrow native-attention request."""

        attention.append(owner)
        return True

    window = OnboardingWindow(
        controller=cast(OnboardingController, controller),
        error_presenter=cast(ErrorReportPresenterProtocol, reports),
        attention_requester=request_attention,
    )
    window.show()

    controller.start_provisioning()
    completion = window._last_completion
    assert completion is not None
    assert window.page_stack.currentWidget() is window.completion_page
    assert window.back_button.isHidden()
    assert window.primary_button.isEnabled()
    assert window.primary_button.text() == "Open Substitute"

    window._go_back()

    assert window.page_stack.currentWidget() is window.completion_page
    assert window.back_button.isHidden()
    assert window.primary_button.isEnabled()
    assert window.primary_button.text() == "Open Substitute"
    window._handle_completion(completion)
    failure = OnboardingProvisioningFailure(
        headline="Setup failed",
        user_message="Try again.",
        technical_detail="failure detail",
        remediation_steps=(),
    )
    window._handle_failure(failure)
    window._handle_failure(failure)

    assert attention == [window, window]
    assert len(reports.reports) == 1
    window._emit_close_requested_on_close = False
    window.close()
