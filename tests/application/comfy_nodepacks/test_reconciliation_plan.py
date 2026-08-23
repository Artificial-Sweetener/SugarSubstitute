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

"""Tests for pure Registry-first core nodepack reconciliation policy."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    CoreNodepackAction,
    RegistryInstallOutcome,
    plan_after_registry_attempt,
    plan_initial_reconciliation,
)
from substitute.domain.comfy_nodepacks import NodepackManagementKind

_PLAN_MODULE = (
    Path(__file__).resolve().parents[3]
    / "substitute"
    / "application"
    / "comfy_nodepacks"
    / "core_nodepack_reconciliation_plan.py"
)
_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
    "urllib",
    "zipfile",
    "shutil",
)


def test_core_nodepack_reconciliation_plan_imports_no_side_effect_boundaries() -> None:
    """Keep lifecycle policy independent from process and filesystem adapters."""

    imported_modules = _imported_module_names(
        ast.parse(_PLAN_MODULE.read_text(encoding="utf-8"))
    )

    assert not {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }


@pytest.mark.parametrize(
    (
        "management",
        "matches",
        "dirty",
        "official_remote",
        "local",
        "refresh",
        "expected",
    ),
    (
        (
            NodepackManagementKind.MISSING,
            False,
            False,
            False,
            True,
            False,
            CoreNodepackAction.USE_LOCAL_SOURCE,
        ),
        (
            NodepackManagementKind.MISSING,
            False,
            False,
            False,
            False,
            False,
            CoreNodepackAction.INSTALL_REGISTRY,
        ),
        (
            NodepackManagementKind.REGISTRY,
            True,
            False,
            False,
            False,
            False,
            CoreNodepackAction.READY,
        ),
        (
            NodepackManagementKind.REGISTRY,
            True,
            False,
            False,
            False,
            True,
            CoreNodepackAction.INSTALL_REGISTRY,
        ),
        (
            NodepackManagementKind.REGISTRY,
            False,
            False,
            False,
            False,
            False,
            CoreNodepackAction.INSTALL_REGISTRY,
        ),
        (
            NodepackManagementKind.GIT,
            True,
            False,
            True,
            False,
            False,
            CoreNodepackAction.MIGRATE_GIT,
        ),
        (
            NodepackManagementKind.GIT,
            True,
            True,
            True,
            False,
            True,
            CoreNodepackAction.READY,
        ),
        (
            NodepackManagementKind.GIT,
            False,
            True,
            True,
            False,
            False,
            CoreNodepackAction.BLOCK_DIRTY,
        ),
        (
            NodepackManagementKind.GIT,
            True,
            False,
            False,
            False,
            False,
            CoreNodepackAction.READY,
        ),
        (
            NodepackManagementKind.GIT,
            False,
            False,
            False,
            False,
            False,
            CoreNodepackAction.BLOCK_UNMANAGED_GIT,
        ),
    ),
)
def test_initial_plan_protects_local_work_and_prefers_registry(
    *,
    management: NodepackManagementKind,
    matches: bool,
    dirty: bool,
    official_remote: bool,
    local: bool,
    refresh: bool,
    expected: CoreNodepackAction,
) -> None:
    """Choose Registry updates while preserving explicit and implicit dev work."""

    assert (
        plan_initial_reconciliation(
            management=management,
            matches_required_version=matches,
            tracked_worktree_dirty=dirty,
            official_git_remote=official_remote,
            local_source_configured=local,
            refresh_requested=refresh,
        )
        is expected
    )


@pytest.mark.parametrize(
    ("outcome", "matches", "expected"),
    (
        (RegistryInstallOutcome.INSTALLED, True, CoreNodepackAction.READY),
        (RegistryInstallOutcome.ALREADY_INSTALLED, True, CoreNodepackAction.READY),
        (
            RegistryInstallOutcome.PENDING_STARTUP,
            False,
            CoreNodepackAction.SETTLE_REGISTRY_UPDATE,
        ),
        (
            RegistryInstallOutcome.VERSION_UNAVAILABLE,
            False,
            CoreNodepackAction.INSTALL_FALLBACK,
        ),
        (
            RegistryInstallOutcome.REGISTRY_UNREACHABLE,
            False,
            CoreNodepackAction.INSTALL_FALLBACK,
        ),
        (RegistryInstallOutcome.FAILED, False, CoreNodepackAction.FAIL),
    ),
)
def test_registry_result_requires_disk_evidence_before_completion(
    *,
    outcome: RegistryInstallOutcome,
    matches: bool,
    expected: CoreNodepackAction,
) -> None:
    """Use inspected CNR state as authority and fallback only on availability failures."""

    assert (
        plan_after_registry_attempt(
            outcome=outcome,
            registry_installation_matches=matches,
        )
        is expected
    )


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
