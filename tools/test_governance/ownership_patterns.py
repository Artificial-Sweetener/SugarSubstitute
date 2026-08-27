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

"""Discover executable-test coupling and import-time resource ownership risks."""

from __future__ import annotations

import ast
from pathlib import Path

from .ast_analysis import call_name
from .model import TestCandidate

SIBLING_IMPORT_RULE = "IMPORT001"
MODULE_RESOURCE_RULE = "SCOPE001"

_MUTABLE_RESOURCE_CONSTRUCTORS = frozenset(
    {
        "concurrent.futures.ProcessPoolExecutor",
        "concurrent.futures.ThreadPoolExecutor",
        "http.server.HTTPServer",
        "http.server.ThreadingHTTPServer",
        "PySide6.QtCore.QProcess",
        "PySide6.QtCore.QThread",
        "PySide6.QtCore.QTimer",
        "PySide6.QtNetwork.QNetworkAccessManager",
        "PySide6.QtWidgets.QApplication",
        "PySide6.QtWidgets.QWidget",
        "socket.socket",
        "subprocess.Popen",
        "tempfile.TemporaryDirectory",
        "threading.Thread",
    }
)


def ownership_pattern_candidates(
    *,
    root: Path,
    test_root: Path,
    source_path: Path,
    relative_path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Return coupling and import-time resource candidates for one source."""

    return [
        *_sibling_test_module_import_candidates(
            root=root,
            test_root=test_root,
            source_path=source_path,
            relative_path=relative_path,
            tree=tree,
        ),
        *_module_resource_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
    ]


def _module_resource_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find mutable process or operating-system resources created at import time."""

    candidates: list[TestCandidate] = []
    ordinal = 0
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        value = statement.value
        if not isinstance(value, ast.Call):
            continue
        constructor = call_name(value.func, aliases)
        if constructor not in _MUTABLE_RESOURCE_CONSTRUCTORS:
            continue
        ordinal += 1
        candidates.append(
            TestCandidate(
                rule=MODULE_RESOURCE_RULE,
                path=path,
                locator=f"<module>:mutable-resource:{ordinal}",
                evidence=f"constructs {constructor} during module import",
                line=statement.lineno,
            )
        )
    return candidates


def _sibling_test_module_import_candidates(
    *,
    root: Path,
    test_root: Path,
    source_path: Path,
    relative_path: str,
    tree: ast.Module,
) -> list[TestCandidate]:
    """Find imports whose resolved owner is another executable test module."""

    candidates: list[TestCandidate] = []
    ordinal = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        imported_paths = _resolved_imported_python_paths(root, source_path, node)
        test_modules = sorted(
            {
                imported_path
                for imported_path in imported_paths
                if imported_path != source_path
                and imported_path.is_relative_to(test_root)
                and imported_path.is_file()
                and imported_path.name.startswith("test_")
            }
        )
        for imported_path in test_modules:
            ordinal += 1
            imported_relative = imported_path.relative_to(root).as_posix()
            candidates.append(
                TestCandidate(
                    rule=SIBLING_IMPORT_RULE,
                    path=relative_path,
                    locator=f"<module>:test-module-import:{ordinal}",
                    evidence=f"imports executable test module {imported_relative}",
                    line=node.lineno,
                )
            )
    return candidates


def _resolved_imported_python_paths(
    root: Path,
    source_path: Path,
    node: ast.Import | ast.ImportFrom,
) -> tuple[Path, ...]:
    """Resolve imported repository Python modules without importing source."""

    if isinstance(node, ast.Import):
        return tuple(
            root.joinpath(*imported.name.split(".")).with_suffix(".py")
            for imported in node.names
        )
    if node.level:
        source_package = source_path.relative_to(root).parent.parts
        keep_count = max(0, len(source_package) - (node.level - 1))
        base_parts = source_package[:keep_count]
    else:
        base_parts = ()
    module_parts = () if node.module is None else tuple(node.module.split("."))
    module_path = root.joinpath(*base_parts, *module_parts)
    imported_paths = [module_path.with_suffix(".py")]
    imported_paths.extend(
        module_path.joinpath(imported.name).with_suffix(".py")
        for imported in node.names
        if imported.name != "*"
    )
    return tuple(imported_paths)


__all__ = [
    "MODULE_RESOURCE_RULE",
    "SIBLING_IMPORT_RULE",
    "ownership_pattern_candidates",
]
