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

"""Enforce the persistent-cache catalog and allocation boundary."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap.persistent_cache_catalog import (
    build_persistent_cache_catalog,
)
from tools.architecture_governance.model import Diagnostic

_CONFIGURATION_COMPATIBILITY_OWNERS = frozenset(
    {
        "substitute/domain/onboarding/models.py",
        "substitute/app/bootstrap/runtime.py",
        "substitute/application/onboarding/installation_service.py",
        "substitute/infrastructure/onboarding/file_installation_repository.py",
        "substitute/infrastructure/onboarding/file_setup_transaction_repository.py",
        "substitute/infrastructure/onboarding/readiness_checks.py",
    }
)
_PREPARED_NAMESPACE_OWNERS = frozenset(
    {
        "substitute/app/bootstrap/persistent_cache_composition.py",
        "substitute/app/bootstrap/runtime.py",
        "substitute/infrastructure/cache_lifecycle/legacy_migration.py",
        "substitute/infrastructure/cache_lifecycle/legacy_model_cache_migration.py",
    }
)
_REQUIRED_AGENTS_GUIDANCE = (
    "## Cache Architecture and Governance",
    "Register every persistent cache",
    "An application version alone is not a cache compatibility input",
)


def validate_cache_governance(root: Path) -> list[Diagnostic]:
    """Return catalog, guidance, and direct-allocation policy diagnostics."""

    diagnostics = _validate_catalog(root)
    diagnostics.extend(_validate_agents_guidance(root))
    diagnostics.extend(validate_cache_path_allocations(root))
    return diagnostics


def validate_cache_path_allocations(root: Path) -> list[Diagnostic]:
    """Reject persistent cache path construction outside the catalog authority."""

    diagnostics: list[Diagnostic] = []
    cache_id_constants = _registered_cache_id_constant_names(root)
    source_root = root / "substitute"
    if not source_root.is_dir():
        return diagnostics
    for path in sorted(source_root.rglob("*.py")):
        relative_path = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except (OSError, UnicodeError, SyntaxError) as error:
            diagnostics.append(
                Diagnostic("CACHE001", relative_path, f"cannot inspect source: {error}")
            )
            continue
        for node in ast.walk(tree):
            if _constructs_from_cache_root(node):
                diagnostics.append(
                    Diagnostic(
                        "CACHE004",
                        relative_path,
                        "persistent cache paths must come from a prepared catalog "
                        f"namespace (line {getattr(node, 'lineno', 0)})",
                    )
                )
            if _is_sqlite_cache_initializer(node) and not _uses_registered_cache_id(
                node,
                cache_id_constants=cache_id_constants,
            ):
                diagnostics.append(
                    Diagnostic(
                        "CACHE007",
                        relative_path,
                        "recoverable SQLite caches must use a registered cache-id "
                        f"constant (line {getattr(node, 'lineno', 0)})",
                    )
                )
            if (
                _is_prepared_namespace_access(node)
                and relative_path not in _PREPARED_NAMESPACE_OWNERS
            ):
                diagnostics.append(
                    Diagnostic(
                        "CACHE008",
                        relative_path,
                        "prepared cache namespaces may be resolved only by cache "
                        f"composition or migration owners "
                        f"(line {getattr(node, 'lineno', 0)})",
                    )
                )
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and node.attr == "model_metadata_dir"
                and relative_path not in _CONFIGURATION_COMPATIBILITY_OWNERS
            ):
                diagnostics.append(
                    Diagnostic(
                        "CACHE005",
                        relative_path,
                        "runtime consumers must use the registered model cache "
                        f"namespaces instead of model_metadata_dir (line {node.lineno})",
                    )
                )
    return diagnostics


def _validate_catalog(root: Path) -> list[Diagnostic]:
    """Build the authoritative catalog and report invalid registrations."""

    try:
        catalog = build_persistent_cache_catalog(source_root=root)
    except (OSError, TypeError, ValueError) as error:
        return [
            Diagnostic(
                "CACHE002",
                "substitute/app/bootstrap/persistent_cache_catalog.py",
                f"persistent cache catalog is invalid: {error}",
            )
        ]
    if not catalog.registrations:
        return [
            Diagnostic(
                "CACHE003",
                "substitute/app/bootstrap/persistent_cache_catalog.py",
                "persistent cache catalog must register every cache owner",
            )
        ]
    return []


def _validate_agents_guidance(root: Path) -> list[Diagnostic]:
    """Keep contributor guidance aligned with executable cache governance."""

    path = root / "AGENTS.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [Diagnostic("CACHE006", "AGENTS.md", f"cannot read guidance: {error}")]
    missing = tuple(
        fragment for fragment in _REQUIRED_AGENTS_GUIDANCE if fragment not in text
    )
    if not missing:
        return []
    return [
        Diagnostic(
            "CACHE006",
            "AGENTS.md",
            f"cache architecture guidance is incomplete; missing {missing[0]!r}",
        )
    ]


def _constructs_from_cache_root(node: ast.AST) -> bool:
    """Return whether one division expression allocates below `cache_dir`."""

    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
        return False
    return any(
        isinstance(candidate, ast.Attribute) and candidate.attr == "cache_dir"
        for candidate in ast.walk(node.left)
    )


def _registered_cache_id_constant_names(root: Path) -> frozenset[str]:
    """Return cache-id constants whose values occur in the production catalog."""

    cache_ids_path = (
        root / "substitute" / "application" / "cache_lifecycle" / "cache_ids.py"
    )
    try:
        tree = ast.parse(cache_ids_path.read_text(encoding="utf-8"))
        registered_ids = {
            item.cache_id
            for item in build_persistent_cache_catalog(source_root=root).registrations
        }
    except (OSError, UnicodeError, SyntaxError, TypeError, ValueError):
        return frozenset()
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and node.value.value in registered_ids
        ):
            names.add(target.id)
    return frozenset(names)


def _is_sqlite_cache_initializer(node: ast.AST) -> bool:
    """Return whether one call opts a SQLite store into cache recovery."""

    return (
        isinstance(node, ast.Call)
        and _call_name(node) == "initialize_recoverable_sqlite"
    )


def _uses_registered_cache_id(
    node: ast.AST,
    *,
    cache_id_constants: frozenset[str],
) -> bool:
    """Return whether one initializer references a catalog-owned identity."""

    if not isinstance(node, ast.Call):
        return False
    for keyword in node.keywords:
        if keyword.arg == "cache_id":
            return isinstance(keyword.value, ast.Name) and (
                keyword.value.id in cache_id_constants
            )
    return False


def _is_prepared_namespace_access(node: ast.AST) -> bool:
    """Return whether one call requests a prepared persistent namespace."""

    return isinstance(node, ast.Call) and _call_name(node) == "namespace"


def _call_name(node: ast.Call) -> str:
    """Return the terminal function name for one direct or attribute call."""

    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


__all__ = ["validate_cache_governance", "validate_cache_path_allocations"]
