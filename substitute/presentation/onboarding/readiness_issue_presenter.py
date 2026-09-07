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

"""Project readiness issues into localized onboarding presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sugarsubstitute_shared.localization import ApplicationText, app_text


class ReadinessIssueLike(Protocol):
    """Describe one readiness issue rendered in onboarding UI."""

    @property
    def code(self) -> object:
        """Return the stable readiness issue code."""

    @property
    def detail(self) -> str:
        """Return technical detail for the issue."""

    @property
    def summary(self) -> str:
        """Return the user-facing summary line."""


@dataclass(frozen=True)
class ReadinessIssuePresentation:
    """Describe the user-facing wording for one readiness issue."""

    headline: ApplicationText
    user_message: ApplicationText
    technical_detail: str


def present_readiness_issue(
    issue: ReadinessIssueLike,
) -> ReadinessIssuePresentation:
    """Return user-facing repair wording for one readiness issue."""

    presentations = {
        "installation_config_missing": ReadinessIssuePresentation(
            headline=app_text("Substitute still needs a home folder"),
            user_message=app_text(
                "Finish setup so Substitute knows where to keep its files."
            ),
            technical_detail="Installation configuration has not been saved yet.",
        ),
        "installation_config_invalid": ReadinessIssuePresentation(
            headline=app_text("Substitute's saved folder settings need to be fixed"),
            user_message=app_text(
                "The stored folder locations no longer match this installation."
            ),
            technical_detail=issue.detail,
        ),
        "runtime_config_missing": ReadinessIssuePresentation(
            headline=app_text("Substitute still needs its local runtime"),
            user_message=app_text(
                "Continue setup so Substitute can prepare the local Python files it needs to run."
            ),
            technical_detail="Runtime configuration has not been created yet.",
        ),
        "runtime_config_invalid": ReadinessIssuePresentation(
            headline=app_text("Substitute's local runtime settings need repair"),
            user_message=app_text(
                "Some saved runtime paths no longer line up with this installation."
            ),
            technical_detail=issue.detail,
        ),
        "runtime_not_provisioned": ReadinessIssuePresentation(
            headline=app_text("Substitute is not fully prepared yet"),
            user_message=app_text(
                "The local runtime has not been set up yet, so the app cannot open normally."
            ),
            technical_detail="The local runtime has not been provisioned.",
        ),
        "runtime_provisioning_incomplete": ReadinessIssuePresentation(
            headline=app_text("Substitute's local setup was interrupted"),
            user_message=app_text(
                "Finish repairing the local runtime before opening the app."
            ),
            technical_detail=issue.detail,
        ),
        "runtime_python_missing": ReadinessIssuePresentation(
            headline=app_text("Local setup is incomplete"),
            user_message=app_text("A required local Python file is missing."),
            technical_detail="Missing runtime Python executable.",
        ),
        "target_config_missing": ReadinessIssuePresentation(
            headline=app_text("Substitute still needs a ComfyUI connection"),
            user_message=app_text(
                "Choose whether Substitute should set up ComfyUI, use an existing copy, or connect to another machine."
            ),
            technical_detail="ComfyUI target configuration has not been saved yet.",
        ),
        "target_config_invalid": ReadinessIssuePresentation(
            headline=app_text("The saved ComfyUI connection needs to be fixed"),
            user_message=app_text(
                "Some required connection details are missing or no longer valid."
            ),
            technical_detail=issue.detail,
        ),
        "managed_workspace_not_configured": ReadinessIssuePresentation(
            headline=app_text("Substitute needs a ComfyUI folder to finish setup"),
            user_message=app_text(
                "Choose where Substitute should place the managed ComfyUI files."
            ),
            technical_detail="Managed local mode is missing its ComfyUI folder path.",
        ),
        "managed_workspace_not_installed": ReadinessIssuePresentation(
            headline=app_text("ComfyUI still needs to be installed"),
            user_message=app_text(
                "The managed ComfyUI setup is not ready yet. Continue repair to install it."
            ),
            technical_detail="Managed ComfyUI workspace is not installed.",
        ),
        "managed_workspace_not_launchable": ReadinessIssuePresentation(
            headline=app_text("ComfyUI needs repair before it can start"),
            user_message=app_text(
                "The managed ComfyUI files are present, but the setup is not ready to launch."
            ),
            technical_detail="Managed ComfyUI workspace is not launchable.",
        ),
        "managed_workspace_not_validated": ReadinessIssuePresentation(
            headline=app_text("ComfyUI still needs hardware validation"),
            user_message=app_text(
                "Substitute has not finished validating the managed backend for this machine yet."
            ),
            technical_detail=issue.detail,
        ),
        "managed_workspace_foreign_listener_blocked": ReadinessIssuePresentation(
            headline=app_text(
                "Another process is already using the saved ComfyUI address"
            ),
            user_message=app_text(
                "Substitute will not start over a different app that is already listening on the managed port."
            ),
            technical_detail=issue.detail,
        ),
        "managed_workspace_backend_invalid": ReadinessIssuePresentation(
            headline=app_text(
                "The managed ComfyUI backend does not match this hardware"
            ),
            user_message=app_text(
                "Repair will re-install ComfyUI with a backend that matches the detected accelerator."
            ),
            technical_detail=issue.detail,
        ),
        "attached_workspace_missing": ReadinessIssuePresentation(
            headline=app_text("The saved ComfyUI folder couldn't be found"),
            user_message=app_text(
                "Check that the local ComfyUI folder still exists, then choose the folder that contains ComfyUI's main.py file."
            ),
            technical_detail=issue.detail,
        ),
        "target_endpoint_invalid": ReadinessIssuePresentation(
            headline=app_text("The saved ComfyUI address needs to be fixed"),
            user_message=app_text(
                "Review the host and port so Substitute knows where to find ComfyUI."
            ),
            technical_detail=issue.detail,
        ),
        "target_endpoint_unreachable": ReadinessIssuePresentation(
            headline=app_text("Substitute couldn't reach the saved ComfyUI address"),
            user_message=app_text(
                "Make sure ComfyUI is running at the saved address, then try again."
            ),
            technical_detail=issue.detail,
        ),
        "backend_compatibility_failed": ReadinessIssuePresentation(
            headline=app_text("The saved ComfyUI runtime needs an extension update"),
            user_message=app_text(
                "Repair the target so Substitute BackEnd and SugarCubes match this version of Substitute."
            ),
            technical_detail=issue.detail,
        ),
        "setup_transaction_interrupted": ReadinessIssuePresentation(
            headline=app_text("Setup was interrupted"),
            user_message=app_text(
                "Continue setup to finish validating the selected ComfyUI runtime."
            ),
            technical_detail=issue.detail,
        ),
        "setup_transaction_failed": ReadinessIssuePresentation(
            headline=app_text("Setup did not finish"),
            user_message=app_text(
                "Review the setup details below, fix the reported issue, and try again."
            ),
            technical_detail=issue.detail,
        ),
        "setup_transaction_corrupt": ReadinessIssuePresentation(
            headline=app_text("Setup state could not be read"),
            user_message=app_text(
                "Start setup again so Substitute can save a clean setup state."
            ),
            technical_detail=issue.detail,
        ),
    }
    return presentations.get(
        getattr(issue, "code").value,
        ReadinessIssuePresentation(
            headline=app_text("Substitute found a setup problem"),
            user_message=app_text(
                "Review the details below and continue through repair to finish setting things up."
            ),
            technical_detail=issue.detail,
        ),
    )


__all__ = [
    "ReadinessIssueLike",
    "ReadinessIssuePresentation",
    "present_readiness_issue",
]
