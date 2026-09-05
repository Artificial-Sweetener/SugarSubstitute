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

"""Provide provisioning progress and setup completion pages."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import (
    render_application_text,
    set_localized_text,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedPushButton,
)


from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    IconWidget,
    IndeterminateProgressBar,
    ProgressBar,
)

from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.terminal.output_view import TerminalOutputView

from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)


class ProvisioningPage(OnboardingPageFrame):
    """Display honest setup progress with an opt-in technical transcript."""

    content_height_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the setup progress page with status-first hierarchy."""

        super().__init__(
            title=app_text("Finishing your setup"),
            description=app_text("The first setup can take a few minutes."),
            icon=FIF.SYNC,
            eyebrow=app_text("Setup in progress"),
            parent=parent,
        )
        self.setObjectName("OnboardingProvisioningPage")
        self._failure_user_message: ApplicationText | None = None
        self._failure_steps: tuple[ApplicationText, ...] = ()
        self._log_expanded = False
        self.content_column.setMinimumWidth(760)

        self.status_panel = QFrame(self)
        self.status_panel.setObjectName("OnboardingStatusPanel")
        self.status_panel.setMinimumWidth(0)
        self.status_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        status_layout = QVBoxLayout(self.status_panel)
        status_layout.setContentsMargins(22, 20, 22, 20)
        status_layout.setSpacing(12)

        self.status_label = LocalizedBodyLabel(
            app_text("Starting setup…"), self.status_panel
        )
        self.status_label.setObjectName("OnboardingProgressStatus")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)

        self.detail_label = LocalizedCaptionLabel(
            app_text(
                "Setup progress appears here. Open the setup log only when you want technical details."
            ),
            self.status_panel,
        )
        self.detail_label.setObjectName("OnboardingStatusDetail")
        self.detail_label.setWordWrap(True)
        status_layout.addWidget(self.detail_label)

        self.overall_progress_label = LocalizedCaptionLabel(
            app_text("Preparing setup tasks…"), self.status_panel
        )
        self.overall_progress_label.setObjectName("OnboardingOverallProgressLabel")
        status_layout.addWidget(self.overall_progress_label)

        self.overall_progress_bar = ProgressBar(self.status_panel, useAni=False)
        self.overall_progress_bar.setObjectName("OnboardingOverallProgressBar")
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setAccessibleName(
            render_application_text(app_text("Overall setup progress"))
        )
        status_layout.addWidget(self.overall_progress_bar)

        self.activity_progress_bar = IndeterminateProgressBar(
            self.status_panel, start=False
        )
        self.activity_progress_bar.setObjectName("OnboardingActivityProgressBar")
        self.activity_progress_bar.setAccessibleName(
            render_application_text(app_text("Setup task activity"))
        )
        status_layout.addWidget(self.activity_progress_bar)

        self.model_progress_label = LocalizedCaptionLabel("", self.status_panel)
        self.model_progress_label.setObjectName("OnboardingModelProgressLabel")
        self.model_progress_label.hide()
        status_layout.addWidget(self.model_progress_label)

        self.model_progress_bar = ProgressBar(self.status_panel, useAni=False)
        self.model_progress_bar.setObjectName("OnboardingModelProgressBar")
        self.model_progress_bar.setRange(0, 100)
        self.model_progress_bar.setValue(0)
        self.model_progress_bar.setAccessibleName(
            render_application_text(app_text("Model download progress"))
        )
        self.model_progress_bar.hide()
        status_layout.addWidget(self.model_progress_bar)

        self.show_log_button = LocalizedPushButton(
            app_text("Show setup log"), self.status_panel
        )
        self.show_log_button.setObjectName("OnboardingShowSetupLogButton")
        self.show_log_button.setCheckable(True)
        self.show_log_button.toggled.connect(self.set_log_expanded)
        status_layout.addWidget(
            self.show_log_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        self.details_container = QWidget(self.status_panel)
        self.details_container.setObjectName("OnboardingSetupLogContainer")
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(8)

        self.output_title_label = LocalizedBodyLabel(
            app_text("Setup log"), self.details_container
        )
        self.output_title_label.setObjectName("OnboardingOutputTitle")
        details_layout.addWidget(self.output_title_label)

        self.details_surface = TerminalOutputView(
            self.details_container,
            min_height=220,
            max_height=280,
        )
        details_layout.addWidget(self.details_surface)
        self.details_container.hide()
        status_layout.addWidget(self.details_container)

        self.body_layout.addWidget(self.status_panel)

    def begin_progress(self) -> None:
        """Prepare the provisioning page for active work."""

        set_localized_text(self.status_label, "Starting setup…")
        set_localized_text(
            self.detail_label,
            "Substitute is preparing ComfyUI. You can keep this window in the background.",
        )
        self.overall_progress_bar.setError(False)
        self.model_progress_bar.setError(False)
        self.activity_progress_bar.setError(False)
        self.activity_progress_bar.start()
        self.activity_progress_bar.show()

    def mark_complete(self) -> None:
        """Render the setup as complete."""

        self.activity_progress_bar.stop()
        self.activity_progress_bar.hide()
        self.overall_progress_bar.setValue(100)
        set_localized_text(self.overall_progress_label, "All setup tasks are complete.")

    def mark_failed(self) -> None:
        """Render the setup as failed without clearing the log output."""

        self.activity_progress_bar.stop()
        self.activity_progress_bar.hide()
        self.overall_progress_bar.setError(True)
        self.model_progress_bar.setError(True)
        self.set_log_expanded(True)

    def reset_progress(self) -> None:
        """Reset the provisioning page state before a retry begins."""

        self._failure_user_message = None
        self._failure_steps = ()
        self.overall_progress_bar.setError(False)
        self.overall_progress_bar.setValue(0)
        self.model_progress_bar.setError(False)
        self.model_progress_bar.setValue(0)
        self.model_progress_bar.hide()
        self.model_progress_label.hide()
        set_localized_text(self.overall_progress_label, "Preparing setup tasks…")
        self.set_log_expanded(False)

    def set_progress(
        self,
        *,
        completed_tasks: int,
        total_tasks: int,
        active: bool,
    ) -> None:
        """Render exact completed-task progress and current activity."""

        safe_total = max(1, total_tasks)
        safe_completed = max(0, min(completed_tasks, safe_total))
        self.overall_progress_bar.setValue(round((safe_completed / safe_total) * 100))
        set_localized_text(
            self.overall_progress_label,
            "%1 of %2 setup tasks complete",
            safe_completed,
            safe_total,
        )
        if active:
            self.activity_progress_bar.start()
            self.activity_progress_bar.show()
        else:
            self.activity_progress_bar.stop()
            self.activity_progress_bar.hide()

    def set_model_download_progress(
        self,
        *,
        completed_bytes: int,
        total_bytes: int,
        current_item: str | None,
        current_item_index: int | None = None,
        total_items: int | None = None,
        complete: bool = False,
    ) -> None:
        """Render exact aggregate model-transfer byte progress."""

        if total_bytes <= 0:
            visibility_changed = self.model_progress_bar.isVisible()
            self.model_progress_bar.hide()
            self.model_progress_label.hide()
            if visibility_changed:
                self.content_height_changed.emit()
            return
        visibility_changed = not self.model_progress_bar.isVisible()
        safe_completed = max(0, min(completed_bytes, total_bytes))
        self.model_progress_bar.setValue(round((safe_completed / total_bytes) * 100))
        self.model_progress_bar.show()
        self.model_progress_label.show()
        completed_mib = safe_completed / (1024 * 1024)
        total_mib = total_bytes / (1024 * 1024)
        if complete:
            set_localized_text(
                self.model_progress_label,
                "Model downloads — %1 of %2 MiB",
                f"{completed_mib:,.1f}",
                f"{total_mib:,.1f}",
            )
        elif (
            current_item and current_item_index is not None and total_items is not None
        ):
            set_localized_text(
                self.model_progress_label,
                "Downloading %1 (%2 of %3) — %4 of %5 MiB",
                current_item,
                current_item_index,
                total_items,
                f"{completed_mib:,.1f}",
                f"{total_mib:,.1f}",
            )
        if visibility_changed:
            self.content_height_changed.emit()
        elif current_item:
            set_localized_text(
                self.model_progress_label,
                "Downloading %1 — %2 of %3 MiB",
                current_item,
                f"{completed_mib:,.1f}",
                f"{total_mib:,.1f}",
            )
        else:
            set_localized_text(
                self.model_progress_label,
                "Model downloads — %1 of %2 MiB",
                f"{completed_mib:,.1f}",
                f"{total_mib:,.1f}",
            )

    def set_log_expanded(self, expanded: bool) -> None:
        """Show or collapse the bounded technical setup transcript."""

        self._log_expanded = expanded
        self.details_container.setVisible(expanded)
        if self.show_log_button.isChecked() != expanded:
            self.show_log_button.setChecked(expanded)
        set_localized_text(
            self.show_log_button,
            "Hide setup log" if expanded else "Show setup log",
        )
        self.content_height_changed.emit()

    def set_output_stream(self, stream: TerminalOutputStream | None) -> None:
        """Bind the shared onboarding output stream to the details surface."""

        self.details_surface.set_stream(stream)

    def append_log(self, line: str) -> None:
        """Append one non-empty log line to the details surface."""

        self.details_surface.append_line(line)

    def clear_details(self) -> None:
        """Reset the rendered details before another provisioning attempt."""

        self.details_surface.clear_output()

    def set_failure_guidance(
        self,
        *,
        user_message: ApplicationText,
        steps: tuple[ApplicationText, ...],
    ) -> None:
        """Render user-facing recovery guidance for a provisioning failure."""

        self._failure_user_message = user_message
        self._failure_steps = steps
        self._render_failure_guidance()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Refresh active failure guidance after an in-place locale switch."""

        super().changeEvent(event)
        if event.type() is QEvent.Type.LanguageChange:
            self._render_failure_guidance()

    def _render_failure_guidance(self) -> None:
        """Render the retained semantic failure guidance in the active locale."""

        user_message = self._failure_user_message
        if user_message is None:
            return
        guidance_lines = [
            render_application_text(user_message),
            *[f"- {render_application_text(step)}" for step in self._failure_steps],
        ]
        self.detail_label.setText("\n".join(line for line in guidance_lines if line))


class CompletionPage(OnboardingPageFrame):
    """Display a confident finish state after setup or repair succeeds."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the completion page with primary success and optional details."""

        super().__init__(
            title=app_text("Substitute is ready"),
            description=app_text(
                "Your setup has been saved. Review the summary below, then open Substitute or close this window if a restart is needed."
            ),
            icon=FIF.ACCEPT,
            eyebrow=app_text("All set"),
            parent=parent,
        )
        self.setObjectName("OnboardingCompletionPage")
        self.success_panel = QFrame(self)
        self.success_panel.setObjectName("OnboardingCompletionSurface")
        self.success_panel.setMinimumWidth(560)
        success_layout = QVBoxLayout(self.success_panel)
        success_layout.setContentsMargins(20, 20, 20, 20)
        success_layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(14)

        badge = QFrame(self.success_panel)
        badge.setObjectName("OnboardingCompletionBadge")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(10, 10, 10, 10)
        badge_layout.setSpacing(0)
        icon_widget = IconWidget(FIF.ACCEPT, badge)
        icon_widget.setFixedSize(28, 28)
        badge_layout.addWidget(icon_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        summary_column = QVBoxLayout()
        summary_column.setContentsMargins(0, 0, 0, 0)
        summary_column.setSpacing(6)

        title_label = LocalizedBodyLabel(app_text("What's ready"), self.success_panel)
        title_label.setObjectName("OnboardingInfoTitle")
        summary_column.addWidget(title_label)

        self.summary_label = LocalizedCaptionLabel("", self.success_panel)
        self.summary_label.setObjectName("OnboardingCompletionSummary")
        self.summary_label.setWordWrap(True)
        summary_column.addWidget(self.summary_label)
        header_row.addLayout(summary_column, 1)
        success_layout.addLayout(header_row)

        self.command_surface = QFrame(self.success_panel)
        self.command_surface.setObjectName("OnboardingCommandSurface")
        command_layout = QVBoxLayout(self.command_surface)
        command_layout.setContentsMargins(16, 14, 16, 14)
        command_layout.setSpacing(8)

        command_title = LocalizedCaptionLabel(
            app_text("Advanced details"), self.command_surface
        )
        command_title.setObjectName("OnboardingFieldLabel")
        command_layout.addWidget(command_title)

        self.command_label = LocalizedBodyLabel("", self.command_surface)
        self.command_label.setObjectName("OnboardingCommandLabel")
        self.command_label.setWordWrap(True)
        self.command_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        command_layout.addWidget(self.command_label)
        success_layout.addWidget(self.command_surface)

        self.body_layout.addWidget(self.success_panel)


__all__ = ["CompletionPage", "ProvisioningPage"]
