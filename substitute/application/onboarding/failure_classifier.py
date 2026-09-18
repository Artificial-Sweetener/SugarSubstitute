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

"""Own data-preserving recovery guidance for onboarding failures."""

from __future__ import annotations
from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.model_acquisition import (
    ModelAcquisitionCredentialRequired,
)
from sugarsubstitute_shared.external_path_failure import (
    ExternalLongPathCompatibilityError,
)
from sugarsubstitute_shared.windows_long_paths import WindowsPathComponentTooLongError
from substitute.domain.onboarding.workspace_conflicts import (
    ManagedWorkspaceConflict,
    ManagedWorkspaceConflictError,
)
from substitute.domain.onboarding import (
    ComfyPythonResolutionError,
    ComfyPythonResolutionFailure,
    ComfyTargetMode,
)
from substitute.application.onboarding.flow_contracts import (
    OnboardingDraftState,
    OnboardingProvisioningFailure,
)
from substitute.domain.onboarding.readiness_models import (
    ReadinessAssessment,
    ReadinessIssue,
    ReadinessIssueCode,
)


class OnboardingFailureClassifier:
    """Translate provisioning and readiness outcomes into actionable guidance."""

    @staticmethod
    def from_readiness(
        *,
        draft: OnboardingDraftState,
        target_mode: ComfyTargetMode,
        assessment: ReadinessAssessment,
    ) -> OnboardingProvisioningFailure:
        """Translate readiness issues into target-specific onboarding failures."""

        issue = assessment.issues[0]
        technical_detail = (
            "\n".join(
                detail
                for detail in (
                    listed_issue.detail for listed_issue in assessment.issues
                )
                if detail
            )
            or issue.summary
        )
        if issue.code is ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING:
            return OnboardingProvisioningFailure(
                headline=app_text("The ComfyUI folder couldn't be found"),
                user_message=app_text(
                    "Substitute couldn't find the local ComfyUI folder you entered."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text("Check that the folder still exists."),
                    app_text("Choose the folder that contains ComfyUI's main.py file."),
                    app_text("Then try again."),
                ),
            )
        if issue.code is ReadinessIssueCode.TARGET_ENDPOINT_UNREACHABLE:
            return OnboardingFailureClassifier._endpoint_unreachable_failure(
                draft=draft,
                target_mode=target_mode,
                technical_detail=technical_detail,
            )
        return OnboardingProvisioningFailure(
            headline=app_text("Substitute couldn't finish this setup"),
            user_message=app_text(
                "Setup details were saved, but Substitute still found a problem that "
                "needs attention before it can continue."
            ),
            technical_detail=technical_detail,
            remediation_steps=tuple(
                OnboardingFailureClassifier._remediation_step_for_issue(
                    issue=listed_issue,
                    draft=draft,
                    target_mode=target_mode,
                )
                for listed_issue in assessment.issues
            ),
        )

    @staticmethod
    def from_exception(
        *,
        draft: OnboardingDraftState,
        target_mode: ComfyTargetMode,
        error: Exception,
    ) -> OnboardingProvisioningFailure:
        """Translate one provisioning exception into actionable onboarding guidance."""

        technical_detail = str(error).strip() or type(error).__name__
        if isinstance(error, ModelAcquisitionCredentialRequired):
            return OnboardingProvisioningFailure(
                headline=app_text("This CivitAI model needs an API key"),
                user_message=app_text(
                    "Your reviewed download plan is still selected. Add a CivitAI API key, then try setup again."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text("Go back to Integrations."),
                    app_text("Add your CivitAI API key."),
                    app_text("Return to setup and try again."),
                ),
            )
        if isinstance(error, WindowsPathComponentTooLongError):
            return OnboardingProvisioningFailure(
                headline=app_text("A file or folder name is too long for Windows"),
                user_message=app_text(
                    "Windows limits each individual file or folder name to 255 characters."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text(
                        "Shorten the file or folder name at %1, then try again.",
                        error.path,
                    ),
                ),
            )
        if isinstance(error, ExternalLongPathCompatibilityError):
            return OnboardingProvisioningFailure(
                headline=app_text("A Windows component could not use this long path"),
                user_message=app_text(
                    "%1 could not use this Windows path even though Substitute can.",
                    error.component,
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text("Choose a shorter folder for this operation."),
                    app_text("Or enable Win32 long paths in Windows, then try again."),
                ),
            )
        if _is_storage_exhaustion_detail(technical_detail):
            return OnboardingProvisioningFailure(
                headline=app_text("Substitute ran out of temporary install space"),
                user_message=app_text(
                    "Setup could not finish while downloading or installing Python "
                    "packages for ComfyUI."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text(
                        "Free space on the drive that contains %1.",
                        draft.installation_root,
                    ),
                    app_text(
                        "Or go back and choose an install location on a drive with more free space."
                    ),
                    app_text("Then run setup again."),
                ),
            )
        if target_mode is ComfyTargetMode.MANAGED_LOCAL and (
            isinstance(error, ManagedWorkspaceConflictError)
            or "invalid ComfyUI repository" in technical_detail
        ):
            if (
                isinstance(error, ManagedWorkspaceConflictError)
                and error.reason is ManagedWorkspaceConflict.EXISTING_INSTALLATION
            ):
                return OnboardingProvisioningFailure(
                    headline=app_text("Use your existing ComfyUI installation"),
                    user_message=app_text(
                        "This folder already contains ComfyUI. Choose Use My Current ComfyUI to connect it without replacing its files."
                    ),
                    technical_detail=technical_detail,
                    remediation_steps=(
                        app_text("Go back to My Current ComfyUI."),
                        app_text(
                            "Choose the folder that contains ComfyUI's main.py file."
                        ),
                        app_text("Then run setup again."),
                    ),
                )
            return OnboardingProvisioningFailure(
                headline=app_text("Choose an empty folder for managed ComfyUI"),
                user_message=app_text(
                    "The selected folder contains files that setup cannot replace safely."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text("Go back and choose an empty ComfyUI folder."),
                    app_text("Then run setup again."),
                ),
            )
        if (
            target_mode is ComfyTargetMode.MANAGED_LOCAL
            and "couldn't download ComfyUI" in technical_detail
        ):
            return OnboardingProvisioningFailure(
                headline=app_text("Substitute couldn't download ComfyUI"),
                user_message=app_text(
                    "Setup couldn't download the ComfyUI files it needs."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text("Check your internet connection."),
                    app_text("Make sure the selected folder is writable."),
                    app_text("Then try again."),
                ),
            )
        if (
            target_mode is ComfyTargetMode.MANAGED_LOCAL
            and "Python packages" in technical_detail
        ):
            return OnboardingProvisioningFailure(
                headline=app_text("Substitute couldn't finish installing ComfyUI"),
                user_message=app_text(
                    "ComfyUI was downloaded, but some of its Python packages could not be installed."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text("Check your internet connection."),
                    app_text(
                        "Make sure security software is not blocking Python package downloads."
                    ),
                    app_text("Then try again."),
                ),
            )
        if (
            target_mode is ComfyTargetMode.MANAGED_LOCAL
            and "required custom nodes" in technical_detail
        ):
            return OnboardingProvisioningFailure(
                headline=app_text("Substitute couldn't finish preparing ComfyUI"),
                user_message=app_text(
                    "ComfyUI was installed, but Substitute couldn't finish preparing the required node packs."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text("Check the live output for the custom-node problem."),
                    app_text("Fix the reported issue if you can."),
                    app_text("Then try again."),
                ),
            )
        if target_mode is ComfyTargetMode.MANAGED_LOCAL:
            return OnboardingProvisioningFailure(
                headline=app_text("Substitute couldn't finish setting up ComfyUI"),
                user_message=app_text(
                    "Setup stopped before ComfyUI was ready. Review the setup log for details, then try again."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text(
                        "Make sure the selected folder is writable and has enough free space."
                    ),
                    app_text(
                        "Keep your internet connection available while setup runs."
                    ),
                    app_text("Then try again."),
                ),
            )
        if target_mode is ComfyTargetMode.ATTACHED_LOCAL:
            if isinstance(error, ComfyPythonResolutionError):
                return OnboardingFailureClassifier._attached_python_resolution_failure(
                    error
                )
            if "could not be found" in technical_detail.lower():
                return OnboardingProvisioningFailure(
                    headline=app_text("The ComfyUI folder couldn't be found"),
                    user_message=app_text(
                        "Substitute couldn't find the local ComfyUI folder you entered."
                    ),
                    technical_detail=technical_detail,
                    remediation_steps=(
                        app_text("Check that the folder still exists."),
                        app_text(
                            "Choose the folder that contains ComfyUI's main.py file."
                        ),
                        app_text("Then try again."),
                    ),
                )
            if "did not respond at" in technical_detail.lower():
                return OnboardingFailureClassifier._endpoint_unreachable_failure(
                    draft=draft,
                    target_mode=target_mode,
                    technical_detail=technical_detail,
                )
            return OnboardingProvisioningFailure(
                headline=app_text(
                    "Substitute could not prepare this local ComfyUI setup"
                ),
                user_message=app_text(
                    "Review the existing ComfyUI folder and local address, then try again."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text(
                        "Make sure the folder points to the ComfyUI setup you want Substitute to launch."
                    ),
                    app_text(
                        "Confirm the local host and port are free for Substitute to use."
                    ),
                ),
            )
        return OnboardingProvisioningFailure(
            headline=app_text(
                "Substitute could not finish this remote connection setup"
            ),
            user_message=app_text("Review the remote address details, then try again."),
            technical_detail=technical_detail,
            remediation_steps=(
                app_text("Confirm the remote host and port are correct."),
                app_text(
                    "Make sure this computer can reach the remote ComfyUI server."
                ),
            ),
        )

    @staticmethod
    def _attached_python_resolution_failure(
        error: ComfyPythonResolutionError,
    ) -> OnboardingProvisioningFailure:
        """Translate typed Comfy Python failures into specific recovery guidance."""

        if error.reason is ComfyPythonResolutionFailure.WORKSPACE_INVALID:
            return OnboardingProvisioningFailure(
                headline=app_text("Choose the folder that contains ComfyUI"),
                user_message=app_text(
                    "The selected folder is not a complete ComfyUI installation."
                ),
                technical_detail=error.detail,
                remediation_steps=(
                    app_text("Go back to My Current ComfyUI."),
                    app_text("Choose the folder that contains ComfyUI's main.py file."),
                    app_text("Then run setup again."),
                ),
            )
        if error.reason is ComfyPythonResolutionFailure.AMBIGUOUS:
            return OnboardingProvisioningFailure(
                headline=app_text("Choose which Python this ComfyUI setup uses"),
                user_message=app_text(
                    "Substitute found more than one working Python environment and "
                    "needs you to choose the one ComfyUI uses."
                ),
                technical_detail=error.detail,
                remediation_steps=(
                    app_text("Go back to My Current ComfyUI."),
                    app_text(
                        "Use Browse beside Python executable and choose this ComfyUI setup's Python."
                    ),
                    app_text("Then run setup again."),
                ),
            )
        if error.reason is ComfyPythonResolutionFailure.EXPLICIT_SELECTION_INVALID:
            return OnboardingProvisioningFailure(
                headline=app_text("Choose a working Python for this ComfyUI setup"),
                user_message=app_text(
                    "The Python executable you selected could not run this ComfyUI "
                    "installation."
                ),
                technical_detail=error.detail,
                remediation_steps=(
                    app_text("Go back to My Current ComfyUI."),
                    app_text(
                        "Use Browse beside Python executable and choose the Python ComfyUI actually uses."
                    ),
                    app_text("Then run setup again."),
                ),
            )
        return OnboardingProvisioningFailure(
            headline=app_text("Choose the Python this ComfyUI setup uses"),
            user_message=app_text(
                "Substitute could not identify a working Python environment "
                "automatically."
            ),
            technical_detail=error.detail,
            remediation_steps=(
                app_text("Go back to My Current ComfyUI."),
                app_text(
                    "Use Browse beside Python executable and choose the Python ComfyUI uses."
                ),
                app_text("Then run setup again."),
            ),
        )

    @staticmethod
    def _endpoint_unreachable_failure(
        *,
        draft: OnboardingDraftState,
        target_mode: ComfyTargetMode,
        technical_detail: str,
    ) -> OnboardingProvisioningFailure:
        """Build a user-facing failure for an unreachable Comfy endpoint."""

        endpoint_label = f"{draft.endpoint_host}:{draft.endpoint_port}"
        if target_mode is ComfyTargetMode.ATTACHED_LOCAL:
            return OnboardingProvisioningFailure(
                headline=app_text("Substitute couldn't reach your ComfyUI setup"),
                user_message=app_text(
                    "Substitute couldn't connect to the local ComfyUI address you entered."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    app_text("Make sure ComfyUI is running at %1.", endpoint_label),
                    app_text("Check that the host and port match your ComfyUI window."),
                    app_text("Then try again."),
                ),
            )
        return OnboardingProvisioningFailure(
            headline=app_text("Substitute couldn't reach the remote ComfyUI server"),
            user_message=app_text(
                "Substitute couldn't connect to the remote ComfyUI address you entered."
            ),
            technical_detail=technical_detail,
            remediation_steps=(
                app_text(
                    "Make sure a ComfyUI server is running at %1.", endpoint_label
                ),
                app_text(
                    "Check that the host and port are correct from this computer."
                ),
                app_text("Then try again."),
            ),
        )

    @staticmethod
    def _remediation_step_for_issue(
        *,
        issue: ReadinessIssue,
        draft: OnboardingDraftState,
        target_mode: ComfyTargetMode,
    ) -> ApplicationText:
        """Return one short user-facing next step for a readiness issue."""

        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_NOT_INSTALLED:
            return app_text(
                "Run setup again so Substitute can finish installing ComfyUI."
            )
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_NOT_LAUNCHABLE:
            return app_text(
                "Run setup again after fixing the files mentioned in the live output."
            )
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_NODEPACKS_MISSING:
            return app_text(
                "Run setup again so Substitute can install its required Comfy nodepacks."
            )
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_NOT_VALIDATED:
            return app_text(
                "Run setup again so Substitute can validate the managed backend on this machine."
            )
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_FOREIGN_LISTENER_BLOCKED:
            return app_text(
                "Stop the other process using %1:%2, or choose a different managed port.",
                draft.endpoint_host,
                draft.endpoint_port,
            )
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_BACKEND_INVALID:
            return app_text(
                "Run setup again so Substitute can install the correct backend for the detected hardware."
            )
        if issue.code is ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING:
            return app_text(
                "Check that the ComfyUI folder still exists, or clear that field."
            )
        if issue.code is ReadinessIssueCode.TARGET_ENDPOINT_UNREACHABLE:
            return app_text(
                "Make sure ComfyUI is running at %1:%2.",
                draft.endpoint_host,
                draft.endpoint_port,
            )
        if target_mode is ComfyTargetMode.MANAGED_LOCAL:
            return app_text("Check the managed ComfyUI folder and try again.")
        return app_text("Review the connection details and try again.")


def _is_storage_exhaustion_detail(detail: str) -> bool:
    """Return whether an install failure describes exhausted temp storage."""

    normalized = detail.casefold()
    return any(
        marker in normalized
        for marker in (
            "managedinstallstorageerror",
            "temporary install space",
            "no space left on device",
            "oserror(28",
            "[errno 28]",
            "there is not enough space on the disk",
        )
    )
