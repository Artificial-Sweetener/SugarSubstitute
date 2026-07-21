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

"""Tests for ownership-aware ComfyUI dependency reconciliation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.python_requirements_probe import (
    PythonRequirementIssue,
    PythonRequirementsAssessment,
)
from substitute.infrastructure.comfy.workspace_dependency_reconciler import (
    AttachedComfyRequirementsError,
    ComfyWorkspaceDependencyReconciler,
)


class _RecordingProbe:
    """Return ordered requirement assessments and record their target."""

    def __init__(self, *assessments: PythonRequirementsAssessment) -> None:
        """Store ordered assessment evidence."""

        self.assessments = list(assessments)
        self.calls: list[Path] = []

    def assess(
        self,
        *,
        requirements_path: Path,
        python_executable: Path,
        workspace: Path,
        env: Mapping[str, str] | None = None,
    ) -> PythonRequirementsAssessment:
        """Return the next configured assessment."""

        del python_executable, workspace, env
        self.calls.append(requirements_path)
        return self.assessments.pop(0)


class _RecordingInstaller:
    """Record managed dependency mutations without invoking pip."""

    def __init__(self, *, failure: str | None = None) -> None:
        """Configure an optional deterministic install failure."""

        self.failure = failure
        self.calls: list[Path] = []

    def install(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        on_log: object | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Record or fail one managed requirements transaction."""

        del python_executable, on_log, env
        self.calls.append(workspace)
        if self.failure is not None:
            raise RuntimeError(self.failure)


def test_managed_reconciliation_skips_satisfied_environment(tmp_path: Path) -> None:
    """An unchanged environment should avoid a pip transaction."""

    python = _write_contract(tmp_path)
    probe = _RecordingProbe(PythonRequirementsAssessment())
    installer = _RecordingInstaller()

    result = ComfyWorkspaceDependencyReconciler(
        requirements_probe=probe,
        installer=installer,
    ).reconcile_managed(workspace=tmp_path, python_executable=python)

    assert result.changed is False
    assert result.snapshot.version == "0.15.0"
    assert installer.calls == []


def test_managed_reconciliation_repairs_and_reprobes_drift(tmp_path: Path) -> None:
    """Managed dependency drift should be repaired and validated before return."""

    python = _write_contract(tmp_path)
    probe = _RecordingProbe(_missing_numpy(), PythonRequirementsAssessment())
    installer = _RecordingInstaller()

    result = ComfyWorkspaceDependencyReconciler(
        requirements_probe=probe,
        installer=installer,
    ).reconcile_managed(workspace=tmp_path, python_executable=python)

    assert result.changed is True
    assert installer.calls == [tmp_path]
    assert probe.calls == [tmp_path / "requirements.txt"] * 2


def test_failed_managed_reconciliation_is_retryable(tmp_path: Path) -> None:
    """A failed mutation should not suppress a later live reassessment and retry."""

    python = _write_contract(tmp_path)
    first_probe = _RecordingProbe(_missing_numpy())
    first_installer = _RecordingInstaller(failure="interrupted pip")

    with pytest.raises(RuntimeError, match="interrupted pip"):
        ComfyWorkspaceDependencyReconciler(
            requirements_probe=first_probe,
            installer=first_installer,
        ).reconcile_managed(workspace=tmp_path, python_executable=python)

    retry_installer = _RecordingInstaller()
    retry = ComfyWorkspaceDependencyReconciler(
        requirements_probe=_RecordingProbe(
            _missing_numpy(), PythonRequirementsAssessment()
        ),
        installer=retry_installer,
    ).reconcile_managed(workspace=tmp_path, python_executable=python)

    assert retry.changed is True
    assert retry_installer.calls == [tmp_path]


def test_attached_reconciliation_reports_drift_without_mutation(tmp_path: Path) -> None:
    """Attached Comfy requirements should remain under user ownership."""

    python = _write_contract(tmp_path)
    installer = _RecordingInstaller()
    reconciler = ComfyWorkspaceDependencyReconciler(
        requirements_probe=_RecordingProbe(_missing_numpy()),
        installer=installer,
    )

    with pytest.raises(AttachedComfyRequirementsError, match="numpy>=2"):
        reconciler.validate_attached(workspace=tmp_path, python_executable=python)

    assert installer.calls == []


def _missing_numpy() -> PythonRequirementsAssessment:
    """Return deterministic unsatisfied dependency evidence."""

    return PythonRequirementsAssessment(
        (PythonRequirementIssue("numpy>=2", "1.26.4", "version_mismatch", 1),)
    )


def _write_contract(workspace: Path) -> Path:
    """Create one supported checkout and Python fixture."""

    (workspace / "comfyui_version.py").write_text(
        '__version__ = "0.15.0"\n', encoding="utf-8"
    )
    (workspace / "requirements.txt").write_text("numpy>=2\n", encoding="utf-8")
    (workspace / "manager_requirements.txt").write_text(
        "comfyui_manager==4.1b1\n", encoding="utf-8"
    )
    python = workspace / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    return python
