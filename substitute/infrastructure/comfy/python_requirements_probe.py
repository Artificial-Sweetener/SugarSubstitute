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

"""Assess requirement files inside their target Python environment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Final, cast

_PROBE_MARKER: Final[str] = "SUGARSUBSTITUTE_REQUIREMENTS_PROBE="
_PROBE_SCRIPT: Final[str] = r"""
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import re
import sys

try:
    from packaging.requirements import InvalidRequirement, Requirement
except ImportError:
    from pip._vendor.packaging.requirements import InvalidRequirement, Requirement

issues = []
path = Path(sys.argv[1])
for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    line = re.split(r"\s+#", raw_line, maxsplit=1)[0].strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("-"):
        issues.append({"requirement": line, "installed_version": None, "reason": "unsupported_directive", "line": line_number})
        continue
    try:
        requirement = Requirement(line)
    except InvalidRequirement:
        issues.append({"requirement": line, "installed_version": None, "reason": "invalid_requirement", "line": line_number})
        continue
    if requirement.marker is not None and not requirement.marker.evaluate():
        continue
    if requirement.url is not None:
        issues.append({"requirement": line, "installed_version": None, "reason": "unverifiable_direct_reference", "line": line_number})
        continue
    try:
        installed = version(requirement.name)
    except PackageNotFoundError:
        issues.append({"requirement": line, "installed_version": None, "reason": "missing", "line": line_number})
        continue
    if requirement.specifier and not requirement.specifier.contains(installed, prereleases=True):
        issues.append({"requirement": line, "installed_version": installed, "reason": "version_mismatch", "line": line_number})
print("SUGARSUBSTITUTE_REQUIREMENTS_PROBE=" + json.dumps({"issues": issues}, sort_keys=True))
"""


@dataclass(frozen=True, slots=True)
class PythonRequirementIssue:
    """Describe one unsatisfied or unverifiable requirement line."""

    requirement: str
    installed_version: str | None
    reason: str
    line: int


@dataclass(frozen=True, slots=True)
class PythonRequirementsAssessment:
    """Capture requirement satisfaction evidence from one target Python."""

    issues: tuple[PythonRequirementIssue, ...] = ()

    @property
    def satisfied(self) -> bool:
        """Return whether every applicable requirement is satisfied."""

        return not self.issues

    @property
    def summary(self) -> str:
        """Return bounded actionable mismatch evidence."""

        if self.satisfied:
            return "requirements satisfied"
        return "; ".join(
            f"line {issue.line} {issue.requirement!r}: {issue.reason}"
            + (
                f" (installed {issue.installed_version})"
                if issue.installed_version is not None
                else ""
            )
            for issue in self.issues[:20]
        )[-4_000:]


class PythonRequirementsProbe:
    """Run a bounded hidden requirement assessment in the target environment."""

    def assess(
        self,
        *,
        requirements_path: Path,
        python_executable: Path,
        workspace: Path,
        env: Mapping[str, str] | None = None,
    ) -> PythonRequirementsAssessment:
        """Return live satisfaction evidence for one requirements file."""

        result = subprocess.run(
            [
                os.path.abspath(python_executable),
                "-c",
                _PROBE_SCRIPT,
                str(requirements_path.resolve()),
            ],
            cwd=str(workspace),
            env=dict(env) if env is not None else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
        if result.returncode != 0:
            detail = " ".join(
                line.strip()
                for output in (result.stdout, result.stderr)
                for line in output.splitlines()
                if line.strip()
            )[-4_000:]
            raise RuntimeError(
                f"Could not assess Python requirements {requirements_path}. {detail}"
            )
        payload = _probe_payload(result.stdout)
        if payload is None:
            raise RuntimeError(
                f"Python requirements probe returned no evidence for {requirements_path}."
            )
        raw_issues = payload.get("issues")
        if not isinstance(raw_issues, list):
            raise RuntimeError("Python requirements probe returned invalid evidence.")
        return PythonRequirementsAssessment(
            tuple(_parse_issue(item) for item in raw_issues)
        )


def _probe_payload(output: str) -> dict[str, object] | None:
    """Return the final marker-prefixed JSON object from probe output."""

    for line in reversed(output.splitlines()):
        if not line.startswith(_PROBE_MARKER):
            continue
        try:
            payload = json.loads(line.removeprefix(_PROBE_MARKER))
        except json.JSONDecodeError:
            return None
        return cast("dict[str, object]", payload) if isinstance(payload, dict) else None
    return None


def _parse_issue(value: object) -> PythonRequirementIssue:
    """Validate one issue object returned by the isolated probe."""

    if not isinstance(value, dict):
        raise RuntimeError("Python requirements probe returned an invalid issue.")
    requirement = value.get("requirement")
    installed_version = value.get("installed_version")
    reason = value.get("reason")
    line = value.get("line")
    if not (
        isinstance(requirement, str)
        and (isinstance(installed_version, str) or installed_version is None)
        and isinstance(reason, str)
        and isinstance(line, int)
    ):
        raise RuntimeError("Python requirements probe returned incomplete issue data.")
    return PythonRequirementIssue(requirement, installed_version, reason, line)


__all__ = [
    "PythonRequirementIssue",
    "PythonRequirementsAssessment",
    "PythonRequirementsProbe",
]
