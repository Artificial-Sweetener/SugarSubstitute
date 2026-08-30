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

"""Reject unreviewed executable work before launch-splash visibility."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from tools.splash_first_governance.source_flow import (
    call_name,
    calls,
    calls_without_nested_functions,
    find_function,
    imports,
    nodes_on_boundary_path,
)


@dataclass(frozen=True, slots=True)
class SplashFirstContract:
    """Describe one executable function and its reviewed splash boundary."""

    relative_path: Path
    function_name: str
    boundary_call: str
    allowed_module_import_roots: frozenset[str]
    allowed_pre_boundary_imports: frozenset[str]
    allowed_pre_boundary_calls: frozenset[str]


@dataclass(frozen=True, slots=True)
class SplashFirstDiagnostic:
    """Identify one source location that violates splash-first startup."""

    path: Path
    line: int
    code: str
    message: str


def repository_contracts() -> tuple[SplashFirstContract, ...]:
    """Return the authoritative executable startup contracts."""

    stdlib_roots = frozenset(
        {
            "__future__",
            "collections",
            "logging",
            "os",
            "pathlib",
            "sys",
            "time",
            "typing",
        }
    )
    return (
        SplashFirstContract(
            relative_path=Path("main.py"),
            function_name="main",
            boundary_call="start_early_launch_splash",
            allowed_module_import_roots=stdlib_roots,
            allowed_pre_boundary_imports=frozenset(
                {
                    "substitute.app.bootstrap.early_launch_splash",
                    "sugarsubstitute_shared.localization",
                }
            ),
            allowed_pre_boundary_calls=frozenset(
                {
                    "Path",
                    "Path.resolve",
                    "_enter_application_launch_guard",
                    "resolve",
                    "resolve_early_startup_locale",
                    "start_early_launch_splash",
                    "system_ui_languages",
                    "time.perf_counter",
                }
            ),
        ),
        SplashFirstContract(
            relative_path=Path("launcher/sugarsubstitute_launcher/app.py"),
            function_name="main",
            boundary_call="start_launcher_splash_session",
            allowed_module_import_roots=stdlib_roots,
            allowed_pre_boundary_imports=frozenset(
                {
                    "launcher.sugarsubstitute_launcher.active_instance_dialog",
                    "launcher.sugarsubstitute_launcher.application_launch",
                    "launcher.sugarsubstitute_launcher.cli",
                    "launcher.sugarsubstitute_launcher.localization",
                    "launcher.sugarsubstitute_launcher.splash_session",
                    "launcher.sugarsubstitute_launcher.startup_plan",
                    "sugarsubstitute_shared.localization",
                }
            ),
            allowed_pre_boundary_calls=frozenset(
                {
                    "Path",
                    "Path.cwd",
                    "_frozen_invocation_path",
                    "_frozen_support_path",
                    "_native_frozen_executable_path",
                    "begin_installed_application_launch",
                    "format_locale_argument",
                    "launch_session.claim_application",
                    "launch_session.release",
                    "negotiate_active_application",
                    "parse_launcher_args",
                    "resolve_launcher_locale",
                    "resolve_startup_candidate",
                    "should_attempt_installed_app_launch",
                    "start_launcher_splash_session",
                }
            ),
        ),
    )


def validate_repository(repository_root: Path) -> tuple[SplashFirstDiagnostic, ...]:
    """Validate every executable contract against repository source."""

    diagnostics: list[SplashFirstDiagnostic] = []
    for contract in repository_contracts():
        path = repository_root / contract.relative_path
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as error:
            diagnostics.append(
                SplashFirstDiagnostic(
                    path=path,
                    line=1,
                    code="SPLASH001",
                    message=f"cannot read protected startup source: {error}",
                )
            )
            continue
        diagnostics.extend(
            validate_contract_source(source, contract=contract, path=path)
        )
    return tuple(diagnostics)


def validate_contract_source(
    source: str,
    *,
    contract: SplashFirstContract,
    path: Path,
) -> tuple[SplashFirstDiagnostic, ...]:
    """Return deterministic diagnostics for one protected startup function."""

    try:
        module = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        return (
            SplashFirstDiagnostic(
                path=path,
                line=error.lineno or 1,
                code="SPLASH001",
                message=f"cannot parse protected startup source: {error.msg}",
            ),
        )

    diagnostics = _module_import_diagnostics(module, contract=contract, path=path)
    diagnostics.extend(
        _module_execution_diagnostics(module, contract=contract, path=path)
    )
    function = find_function(module, contract.function_name)
    if function is None:
        diagnostics.append(
            SplashFirstDiagnostic(
                path=path,
                line=1,
                code="SPLASH001",
                message=(
                    f"protected startup function is missing: {contract.function_name}"
                ),
            )
        )
        return tuple(diagnostics)

    boundary_calls = tuple(
        call
        for call in calls_without_nested_functions(function)
        if call_name(call) == contract.boundary_call
    )
    if len(boundary_calls) != 1:
        diagnostics.append(
            SplashFirstDiagnostic(
                path=path,
                line=function.lineno,
                code="SPLASH001",
                message=(
                    "protected startup function must contain exactly one "
                    f"{contract.boundary_call}() visibility boundary; found "
                    f"{len(boundary_calls)}"
                ),
            )
        )
        return tuple(diagnostics)

    boundary = boundary_calls[0]
    pre_boundary_nodes = nodes_on_boundary_path(function, boundary)
    for imported_name, node in imports(pre_boundary_nodes):
        if _matches_import(imported_name, contract.allowed_pre_boundary_imports):
            continue
        diagnostics.append(
            SplashFirstDiagnostic(
                path=path,
                line=node.lineno,
                code="SPLASH003",
                message=(
                    f"unreviewed pre-splash import {imported_name!r}; move it after "
                    f"{contract.boundary_call}() or add an explicitly reviewed owner"
                ),
            )
        )

    for call in calls(pre_boundary_nodes):
        if call is boundary:
            continue
        reviewed_call_name = call_name(call)
        if reviewed_call_name in contract.allowed_pre_boundary_calls:
            continue
        diagnostics.append(
            SplashFirstDiagnostic(
                path=path,
                line=call.lineno,
                code="SPLASH004",
                message=(
                    "unreviewed pre-splash call "
                    f"{reviewed_call_name or '<dynamic>'}(); "
                    f"move it after {contract.boundary_call}()"
                ),
            )
        )
    return tuple(
        sorted(diagnostics, key=lambda item: (item.line, item.code, item.message))
    )


def _module_import_diagnostics(
    module: ast.Module,
    *,
    contract: SplashFirstContract,
    path: Path,
) -> list[SplashFirstDiagnostic]:
    """Reject eager project and third-party imports in protected entry modules."""

    diagnostics: list[SplashFirstDiagnostic] = []
    for statement in module.body:
        if not isinstance(statement, (ast.Import, ast.ImportFrom)):
            continue
        for imported_name, node in imports((statement,)):
            root = imported_name.split(".", maxsplit=1)[0]
            if root in contract.allowed_module_import_roots:
                continue
            diagnostics.append(
                SplashFirstDiagnostic(
                    path=path,
                    line=node.lineno,
                    code="SPLASH002",
                    message=(
                        f"eager import {imported_name!r} runs before splash routing; "
                        "import it inside the owning post-splash path"
                    ),
                )
            )
    return diagnostics


def _module_execution_diagnostics(
    module: ast.Module,
    *,
    contract: SplashFirstContract,
    path: Path,
) -> list[SplashFirstDiagnostic]:
    """Reject import-time calls outside the protected entrypoint function."""

    diagnostics: list[SplashFirstDiagnostic] = []
    for statement in module.body:
        if isinstance(
            statement,
            (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue
        if _is_type_checking_block(statement) or _is_main_dispatch(
            statement,
            function_name=contract.function_name,
        ):
            continue
        for call in calls((statement,)):
            diagnostics.append(
                SplashFirstDiagnostic(
                    path=path,
                    line=call.lineno,
                    code="SPLASH005",
                    message=(
                        f"import-time call {call_name(call) or '<dynamic>'}() runs "
                        "before splash routing; move it inside the reviewed entrypoint"
                    ),
                )
            )
    return diagnostics


def _is_type_checking_block(statement: ast.stmt) -> bool:
    """Return whether one module statement is a static-only import block."""

    return (
        isinstance(statement, ast.If)
        and isinstance(statement.test, ast.Name)
        and (statement.test.id == "TYPE_CHECKING")
    )


def _is_main_dispatch(statement: ast.stmt, *, function_name: str) -> bool:
    """Return whether one statement only dispatches the protected entrypoint."""

    if not isinstance(statement, ast.If) or statement.orelse:
        return False
    statement_calls = tuple(calls(statement.body))
    return len(statement_calls) == 1 and call_name(statement_calls[0]) == function_name


def _matches_import(imported_name: str, allowed_names: frozenset[str]) -> bool:
    """Return whether an import is the reviewed module or one of its children."""

    return any(
        imported_name == allowed or imported_name.startswith(f"{allowed}.")
        for allowed in allowed_names
    )


__all__ = [
    "SplashFirstContract",
    "SplashFirstDiagnostic",
    "repository_contracts",
    "validate_contract_source",
    "validate_repository",
]
