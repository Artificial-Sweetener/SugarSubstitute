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

"""Define immutable test-governance policy and reviewed state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from tools.architecture_governance.model import Diagnostic


@dataclass(frozen=True, slots=True)
class TestPolicy:
    """Define exact test discovery inputs and registry locations."""

    test_root: Path
    semantic_support_roots: tuple[Path, ...]
    root_source_extensions: frozenset[str]
    allowed_root_source_paths: frozenset[str]
    serial_policy: Path
    wait_calls: frozenset[str]
    wall_clock_calls: frozenset[str]
    xdist_environment_name: str
    repository_scratch_name: str
    debt_registry: Path
    waiver_registry: Path


@dataclass(frozen=True, slots=True)
class TestCandidate:
    """Identify one mechanically discovered fact requiring human review."""

    rule: str
    path: str
    locator: str
    evidence: str
    line: int

    @property
    def key(self) -> str:
        """Return the stable identity used by reviewed state records."""

        return f"{self.rule}|{self.path}|{self.locator}"


@dataclass(frozen=True, slots=True)
class TestDebt:
    """Describe reviewed test debt and its concrete remediation."""

    identifier: str
    owner: str
    rule: str
    candidates: tuple[str, ...]
    paths: tuple[str, ...]
    fingerprint: str
    issue: str
    review_by: date
    problem: str
    remediation: str


@dataclass(frozen=True, slots=True)
class TestWaiver:
    """Describe an exact classification or debt-remediation exception."""

    identifier: str
    owner: str
    kind: str
    disposition: str
    rule: str
    candidates: tuple[str, ...]
    paths: tuple[str, ...]
    fingerprint: str
    rationale: str
    issue: str
    review_by: date
    debt: str | None


@dataclass(frozen=True, slots=True)
class TestState:
    """Collect current test debt and waiver snapshots."""

    debts: tuple[TestDebt, ...]
    waivers: tuple[TestWaiver, ...]


@dataclass(frozen=True, slots=True)
class TestValidationResult:
    """Return discovered candidates together with policy diagnostics."""

    candidates: tuple[TestCandidate, ...]
    diagnostics: tuple[Diagnostic, ...]
