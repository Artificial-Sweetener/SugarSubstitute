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

"""Define immutable architecture governance values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Describe one actionable architecture policy result."""

    rule: str
    path: str
    message: str
    severity: str = "error"

    def render(self) -> str:
        """Render a stable path-oriented diagnostic."""

        return f"{self.path}:1: {self.severity} {self.rule}: {self.message}"


@dataclass(frozen=True, slots=True)
class ArchitecturePolicy:
    """Define the source scope and structural limits."""

    soft_lines: int
    hard_lines: int
    source_roots: tuple[Path, ...]
    source_files: tuple[Path, ...]
    source_extensions: frozenset[str]
    excluded_paths: frozenset[str]
    debt_registry: Path
    waiver_registry: Path


@dataclass(frozen=True, slots=True)
class ArchitectureDebt:
    """Describe current assessed mixed ownership and its next extraction."""

    identifier: str
    owner: str
    paths: tuple[str, ...]
    fingerprint: str
    issue: str
    review_by: date
    responsibilities: tuple[str, ...]
    next_extraction: str


@dataclass(frozen=True, slots=True)
class ArchitectureWaiver:
    """Describe one exact, bounded structural gate exception."""

    identifier: str
    owner: str
    rule: str
    path: str
    kind: str
    justification: str
    issue: str
    review_by: date
    max_lines: int
    next_limit: int | None
    debt: str | None


@dataclass(frozen=True, slots=True)
class ArchitectureState:
    """Collect current debt and waiver snapshots."""

    debts: tuple[ArchitectureDebt, ...]
    waivers: tuple[ArchitectureWaiver, ...]
