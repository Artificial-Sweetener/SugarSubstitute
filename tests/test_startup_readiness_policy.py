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

"""Verify startup readiness retry policy."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap.startup_readiness_policy import (
    STARTUP_READINESS_MAX_ATTEMPTS,
    TRANSIENT_STARTUP_COMPATIBILITY_STATUSES,
    should_retry_startup_compatibility,
)
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
POLICY_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_readiness_policy.py"
)
FORBIDDEN_POLICY_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_retry_policy_retries_transient_backend_unreachable_before_timeout() -> None:
    """Transient compatibility status should retry until readiness attempts expire."""

    assert TRANSIENT_STARTUP_COMPATIBILITY_STATUSES == frozenset(
        {RuntimeCompatibilityStatus.BACKEND_UNREACHABLE}
    )
    assert (
        should_retry_startup_compatibility(
            compatibility=_compatibility(
                RuntimeCompatibilityStatus.BACKEND_UNREACHABLE
            ),
            readiness_attempts=STARTUP_READINESS_MAX_ATTEMPTS - 1,
        )
        is True
    )


def test_retry_policy_stops_after_timeout_or_nontransient_status() -> None:
    """Non-transient or exhausted compatibility states should fail readiness."""

    assert (
        should_retry_startup_compatibility(
            compatibility=_compatibility(
                RuntimeCompatibilityStatus.BACKEND_UNREACHABLE
            ),
            readiness_attempts=STARTUP_READINESS_MAX_ATTEMPTS,
        )
        is False
    )
    assert (
        should_retry_startup_compatibility(
            compatibility=_compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD),
            readiness_attempts=0,
        )
        is False
    )


def test_startup_readiness_policy_imports_no_forbidden_boundaries() -> None:
    """Readiness retry policy must stay free of Qt, presentation, and infrastructure."""

    imported_modules = _imported_module_names(POLICY_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_POLICY_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_readiness_retry_policy() -> None:
    """The startup facade should delegate compatibility retry decisions."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "_TRANSIENT_STARTUP_COMPATIBILITY_STATUSES" not in source
    assert "_STARTUP_READINESS_MAX_ATTEMPTS" not in source
    assert "def _should_retry_startup_compatibility" not in source


def _compatibility(status: RuntimeCompatibilityStatus) -> BackendCompatibilityResult:
    """Build a runtime compatibility result for readiness policy tests."""

    return BackendCompatibilityResult(
        status=status,
        summary=status.value,
        installed_backend_version="",
        required_backend_version=">=1.6.2,<2.0.0",
        installed_sugarcubes_version="",
        required_sugarcubes_version="0.11.0",
        repairable=False,
    )
