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

"""Tests for pure core nodepack reconciliation plans."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    CoreNodepackDependencyRefreshPlan,
    CoreNodepackInstallRoute,
    CoreNodepackRefreshRoute,
    plan_core_nodepack_dependency_refresh,
    plan_core_nodepack_install_route,
    plan_core_nodepack_refresh_route,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "comfy_nodepacks"
    / "core_nodepack_reconciliation_plan.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
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
    """Core nodepack plans must stay pure and host-portable."""

    imported_modules = _imported_module_names(
        ast.parse(PLAN_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


@pytest.mark.parametrize(
    (
        "registry_available",
        "source_url",
        "local_source_available",
        "expected",
    ),
    (
        (
            True,
            "https://example.invalid/source.git",
            True,
            CoreNodepackInstallRoute(source="registry", install_id="nodepack-id"),
        ),
        (
            False,
            "https://example.invalid/source.git",
            True,
            CoreNodepackInstallRoute(
                source="source_url",
                install_id="https://example.invalid/source.git",
            ),
        ),
        (
            False,
            None,
            True,
            CoreNodepackInstallRoute(source="local_source", install_id=None),
        ),
        (
            False,
            None,
            False,
            CoreNodepackInstallRoute(source="unavailable", install_id=None),
        ),
    ),
)
def test_plan_core_nodepack_install_route_prioritizes_sources(
    *,
    registry_available: bool,
    source_url: str | None,
    local_source_available: bool,
    expected: CoreNodepackInstallRoute,
) -> None:
    """Install plans should prefer registry, then source URL, then local source."""

    assert (
        plan_core_nodepack_install_route(
            registry_id="nodepack-id",
            registry_available=registry_available,
            source_url=source_url,
            local_source_available=local_source_available,
        )
        == expected
    )


@pytest.mark.parametrize(
    (
        "git_managed",
        "git_refresh_succeeded",
        "pinned_archive_available",
        "registry_available",
        "source_url",
        "local_source_available",
        "expected",
    ),
    (
        (
            True,
            None,
            True,
            True,
            "https://example.invalid/source.git",
            True,
            CoreNodepackRefreshRoute(source="git_refresh", install_id=None),
        ),
        (
            True,
            True,
            True,
            True,
            "https://example.invalid/source.git",
            True,
            CoreNodepackRefreshRoute(source="git_refreshed", install_id=None),
        ),
        (
            True,
            False,
            True,
            True,
            "https://example.invalid/source.git",
            True,
            CoreNodepackRefreshRoute(source="pinned_archive", install_id=None),
        ),
        (
            True,
            False,
            False,
            True,
            "https://example.invalid/source.git",
            True,
            CoreNodepackRefreshRoute(source="registry", install_id="nodepack-id"),
        ),
        (
            False,
            None,
            False,
            False,
            "https://example.invalid/source.git",
            True,
            CoreNodepackRefreshRoute(
                source="source_url",
                install_id="https://example.invalid/source.git",
            ),
        ),
        (
            False,
            None,
            False,
            False,
            None,
            True,
            CoreNodepackRefreshRoute(source="local_source", install_id=None),
        ),
        (
            False,
            None,
            False,
            False,
            None,
            False,
            CoreNodepackRefreshRoute(source="unavailable", install_id=None),
        ),
    ),
)
def test_plan_core_nodepack_refresh_route_prioritizes_sources(
    *,
    git_managed: bool,
    git_refresh_succeeded: bool | None,
    pinned_archive_available: bool,
    registry_available: bool,
    source_url: str | None,
    local_source_available: bool,
    expected: CoreNodepackRefreshRoute,
) -> None:
    """Refresh plans should prefer git, then pinned archive, then install fallbacks."""

    assert (
        plan_core_nodepack_refresh_route(
            registry_id="nodepack-id",
            git_managed=git_managed,
            git_refresh_succeeded=git_refresh_succeeded,
            pinned_archive_available=pinned_archive_available,
            registry_available=registry_available,
            source_url=source_url,
            local_source_available=local_source_available,
        )
        == expected
    )


@pytest.mark.parametrize(
    (
        "minimum_satisfied",
        "pinned_archive_available",
        "pinned_fallback_already_applied",
        "expected",
    ),
    (
        (
            True,
            False,
            False,
            CoreNodepackDependencyRefreshPlan(action="ready"),
        ),
        (
            False,
            True,
            False,
            CoreNodepackDependencyRefreshPlan(action="pinned_fallback"),
        ),
        (
            False,
            False,
            False,
            CoreNodepackDependencyRefreshPlan(action="failed"),
        ),
        (
            False,
            True,
            True,
            CoreNodepackDependencyRefreshPlan(action="failed"),
        ),
    ),
)
def test_plan_core_nodepack_dependency_refresh_selects_next_action(
    *,
    minimum_satisfied: bool,
    pinned_archive_available: bool,
    pinned_fallback_already_applied: bool,
    expected: CoreNodepackDependencyRefreshPlan,
) -> None:
    """Dependency plans should allow one pinned fallback before failing."""

    assert (
        plan_core_nodepack_dependency_refresh(
            minimum_satisfied=minimum_satisfied,
            pinned_archive_available=pinned_archive_available,
            pinned_fallback_already_applied=pinned_fallback_already_applied,
        )
        == expected
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
