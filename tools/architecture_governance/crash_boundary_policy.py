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

"""Enforce explicit ownership for process, thread, task, and crash boundaries."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .crash_boundary_inventory import REVIEWED_CRASH_BOUNDARY_ROWS
from .metrics import governed_source_paths
from .model import ArchitecturePolicy, Diagnostic


@dataclass(frozen=True, slots=True, order=True)
class CrashBoundarySite:
    """Identify one authored boundary primitive by stable source ownership."""

    category: str
    path: str
    owner: str
    primitive: str
    occurrence: int


_REVIEWED_SITES = {
    CrashBoundarySite(category, path, owner, primitive, occurrence): disposition
    for category, path, owner, primitive, occurrence, disposition in REVIEWED_CRASH_BOUNDARY_ROWS
}
_ALLOWED_SITES = frozenset(_REVIEWED_SITES)
_ALLOWED_DISPOSITIONS_BY_CATEGORY = {
    "application": frozenset(
        {
            "developer_only_ui",
            "isolated_support_ui",
            "recovery_bound_crash_reporter",
            "supervised_launcher_ui",
        }
    ),
    "application_class": frozenset({"process_crash_runtime"}),
    "async_task": frozenset(
        {
            "bounded_observed_futures",
            "managed_task_outcomes",
            "signal_reported_install_worker",
        }
    ),
    "crash_hook": frozenset(
        {
            "authoritative_fault_trace",
            "external_guardian_shutdown_signal",
            "graceful_shutdown_signal",
        }
    ),
    "executor": frozenset({"bounded_observed_futures", "managed_task_outcomes"}),
    "hard_exit": frozenset(
        {
            "controlled_developer_entrypoint_exit",
            "controlled_launcher_entrypoint_exit",
            "external_guardian_control",
            "external_guardian_entrypoint",
            "external_process_liveness_probe",
            "graceful_shutdown_exit",
            "isolated_clone_entrypoint",
            "isolated_support_entrypoint",
            "parent_liveness_probe",
            "process_liveness_probe",
            "source_supervisor_outcome",
            "supervised_clean_exit",
            "transactional_update_entrypoint",
            "transactional_update_handoff",
        }
    ),
    "process": frozenset(
        {
            "application_supervisor_adapter",
            "external_comfy_command",
            "external_comfy_guardian",
            "external_comfy_install_command",
            "external_comfy_probe",
            "external_comfy_process",
            "external_environment_command",
            "external_environment_validation",
            "external_extraction_tool",
            "external_hardware_probe",
            "external_install_command",
            "external_process_control",
            "external_process_query",
            "external_python_probe",
            "external_runtime_install_command",
            "external_runtime_provisioning",
            "external_tool_process",
            "external_version_control_command",
            "independent_crash_reporter",
            "isolated_support_process",
            "operating_system_shell",
            "supervised_launcher_handoff",
            "supervised_restart_launcher",
            "transactional_launcher_handoff",
        }
    ),
    "process_handoff": frozenset(
        {
            "supervised_launcher_handoff",
            "supervised_restart_launcher",
            "transactional_launcher_handoff",
            "transactional_update_handoff",
        }
    ),
    "python_crash_hook": frozenset({"authoritative_crash_hook"}),
    "qt_fatal_hook": frozenset(
        {"authoritative_qt_hook_install", "authoritative_qt_hook_probe"}
    ),
    "qt_thread": frozenset({"managed_task_outcomes", "signal_reported_install_worker"}),
    "qt_thread_class": frozenset(
        {"managed_task_outcomes", "signal_reported_install_worker"}
    ),
    "thread": frozenset(
        {
            "bounded_process_output",
            "bounded_transport_thread",
            "external_guardian_thread",
            "managed_host_diagnostics",
            "managed_host_scheduler",
            "managed_task_outcomes",
        }
    ),
    "thread_class": frozenset(
        {
            "bounded_transport_thread",
            "external_guardian_thread",
            "managed_task_outcomes",
        }
    ),
}
_RUNTIME_ROOTS = frozenset({"launcher", "substitute", "sugarsubstitute_shared"})
_EXACT_RUNTIME_FILES = frozenset({"main.py", "sitecustomize.py"})
_CALL_CATEGORIES = {
    "subprocess.Popen": "process",
    "subprocess.run": "process",
    "subprocess.call": "process",
    "subprocess.check_call": "process",
    "subprocess.check_output": "process",
    "subprocess.getoutput": "process",
    "subprocess.getstatusoutput": "process",
    "multiprocessing.Process": "process",
    "multiprocessing.Pool": "process",
    "multiprocessing.context.BaseContext.Process": "process",
    "multiprocessing.context.BaseContext.Pool": "process",
    "asyncio.create_subprocess_exec": "process",
    "asyncio.create_subprocess_shell": "process",
    "PySide6.QtCore.QProcess": "process",
    "PySide6.QtCore.QProcess.startDetached": "process",
    "os.system": "process",
    "os.popen": "process",
    "os.startfile": "process",
    "os.posix_spawn": "process",
    "os.posix_spawnp": "process",
    "os.spawnl": "process",
    "os.spawnle": "process",
    "os.spawnlp": "process",
    "os.spawnlpe": "process",
    "os.spawnv": "process",
    "os.spawnve": "process",
    "os.spawnvp": "process",
    "os.spawnvpe": "process",
    "os.execl": "process_handoff",
    "os.execle": "process_handoff",
    "os.execlp": "process_handoff",
    "os.execlpe": "process_handoff",
    "os.execv": "process_handoff",
    "os.execve": "process_handoff",
    "os.execvp": "process_handoff",
    "os.execvpe": "process_handoff",
    "threading.Thread": "thread",
    "concurrent.futures.ThreadPoolExecutor": "executor",
    "concurrent.futures.ProcessPoolExecutor": "executor",
    "concurrent.futures.ThreadPoolExecutor.submit": "async_task",
    "concurrent.futures.ProcessPoolExecutor.submit": "async_task",
    "PySide6.QtCore.QThread": "qt_thread",
    "PySide6.QtCore.QRunnable": "qt_thread",
    "PySide6.QtCore.QThreadPool": "qt_thread",
    "PySide6.QtCore.QThreadPool.start": "async_task",
    "PySide6.QtCore.QThreadPool.tryStart": "async_task",
    "PySide6.QtConcurrent.QtConcurrent.run": "async_task",
    "asyncio.create_task": "async_task",
    "asyncio.ensure_future": "async_task",
    "asyncio.TaskGroup.create_task": "async_task",
    "asyncio.AbstractEventLoop.create_task": "async_task",
    "asyncio.AbstractEventLoop.run_in_executor": "async_task",
    "asyncio.run_coroutine_threadsafe": "async_task",
    "PySide6.QtWidgets.QApplication": "application",
    "PySide6.QtCore.QCoreApplication": "application",
    "PySide6.QtGui.QGuiApplication": "application",
    "PySide6.QtCore.qInstallMessageHandler": "qt_fatal_hook",
    "signal.signal": "crash_hook",
    "faulthandler.enable": "crash_hook",
    "faulthandler.disable": "crash_hook",
    "faulthandler.register": "crash_hook",
    "faulthandler.unregister": "crash_hook",
    "sys.exit": "hard_exit",
    "os._exit": "hard_exit",
    "os.abort": "hard_exit",
    "os.kill": "hard_exit",
    "signal.raise_signal": "hard_exit",
}
_HOOK_TARGETS = {
    "sys.excepthook": "python_crash_hook",
    "threading.excepthook": "python_crash_hook",
    "sys.unraisablehook": "python_crash_hook",
}
_CLASS_BASE_CATEGORIES = {
    "threading.Thread": "thread_class",
    "PySide6.QtWidgets.QApplication": "application_class",
    "PySide6.QtCore.QCoreApplication": "application_class",
    "PySide6.QtGui.QGuiApplication": "application_class",
    "PySide6.QtCore.QThread": "qt_thread_class",
    "PySide6.QtCore.QRunnable": "qt_thread_class",
}
_FACTORY_RESULT_TYPES = {
    "asyncio.get_event_loop": "asyncio.AbstractEventLoop",
    "asyncio.get_running_loop": "asyncio.AbstractEventLoop",
    "asyncio.new_event_loop": "asyncio.AbstractEventLoop",
    "concurrent.futures.ProcessPoolExecutor": (
        "concurrent.futures.ProcessPoolExecutor"
    ),
    "concurrent.futures.ThreadPoolExecutor": ("concurrent.futures.ThreadPoolExecutor"),
    "multiprocessing.get_context": "multiprocessing.context.BaseContext",
    "PySide6.QtCore.QThreadPool": "PySide6.QtCore.QThreadPool",
    "PySide6.QtCore.QThreadPool.globalInstance": "PySide6.QtCore.QThreadPool",
}


def validate_crash_boundary_policy(
    root: Path, policy: ArchitecturePolicy
) -> list[Diagnostic]:
    """Reject new or removed raw boundaries outside the reviewed inventory."""

    discovered = discover_crash_boundary_sites(root, policy)
    diagnostics = validate_crash_boundary_inventory(REVIEWED_CRASH_BOUNDARY_ROWS)
    diagnostics.extend(
        Diagnostic(
            "CRASH001",
            site.path,
            f"{site.primitive} in {site.owner} creates a {site.category} boundary "
            "without an explicit crash-participation classification",
        )
        for site in sorted(discovered - _ALLOWED_SITES)
    )
    if (root / "sugarsubstitute_shared/crash_reporting/runtime.py").is_file():
        diagnostics.extend(
            Diagnostic(
                "CRASH002",
                site.path,
                f"reviewed {site.primitive} boundary in {site.owner} no longer exists; "
                "remove or reassess its crash-participation classification",
            )
            for site in sorted(_ALLOWED_SITES - discovered)
        )
    return diagnostics


def validate_crash_boundary_inventory(
    rows: tuple[tuple[str, str, str, str, int, str], ...],
) -> list[Diagnostic]:
    """Reject duplicate sites and dispositions outside the reviewed vocabulary."""

    diagnostics: list[Diagnostic] = []
    seen: set[CrashBoundarySite] = set()
    for category, path, owner, primitive, occurrence, disposition in rows:
        site = CrashBoundarySite(category, path, owner, primitive, occurrence)
        if site in seen:
            diagnostics.append(
                Diagnostic(
                    "CRASH003",
                    path,
                    f"duplicate crash boundary inventory site: {primitive} in {owner}",
                )
            )
        seen.add(site)
        allowed = _ALLOWED_DISPOSITIONS_BY_CATEGORY.get(category, frozenset())
        if disposition not in allowed:
            diagnostics.append(
                Diagnostic(
                    "CRASH003",
                    path,
                    f"{disposition!r} is not an approved {category} participation disposition",
                )
            )
    return diagnostics


def discover_crash_boundary_sites(
    root: Path, policy: ArchitecturePolicy
) -> frozenset[CrashBoundarySite]:
    """Return every raw crash-relevant boundary in authored runtime source."""

    sites: set[CrashBoundarySite] = set()
    for path in governed_source_paths(root, policy):
        relative = path.relative_to(root).as_posix()
        first_part = Path(relative).parts[0]
        if first_part not in _RUNTIME_ROOTS and relative not in _EXACT_RUNTIME_FILES:
            continue
        if path.suffix not in {".py", ".pyi"}:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        visitor = _BoundaryVisitor(relative)
        visitor.visit(tree)
        sites.update(visitor.sites)
    return frozenset(sites)


class _BoundaryVisitor(ast.NodeVisitor):
    """Resolve imports and collect stable enclosing-owner boundary sites."""

    def __init__(self, path: str) -> None:
        """Prepare one source-file traversal."""

        self._path = path
        self._aliases: dict[str, str] = {}
        self._bindings: list[dict[str, str]] = [{}]
        self._owners: list[str] = []
        self._occurrences: dict[tuple[str, str, str], int] = {}
        self.sites: set[CrashBoundarySite] = set()

    def visit_Import(self, node: ast.Import) -> None:
        """Record module aliases used to qualify primitives."""

        for alias in node.names:
            self._aliases[alias.asname or alias.name.split(".")[0]] = alias.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Record directly imported primitives."""

        if node.module is None:
            return
        for alias in node.names:
            self._aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class ownership and raw boundary inheritance."""

        for base in node.bases:
            primitive = self._resolved_name(base)
            category = _CLASS_BASE_CATEGORIES.get(primitive)
            if category is not None:
                self._owners.append(node.name)
                self._record(category, primitive)
                self._owners.pop()
        self._visit_owned(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function ownership while visiting its body."""

        self._visit_owned(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track asynchronous function ownership while visiting its body."""

        self._visit_owned(node, node.name)

    def visit_Call(self, node: ast.Call) -> None:
        """Record recognized construction and hook calls."""

        primitive = self._resolved_name(node.func)
        category = _CALL_CATEGORIES.get(primitive)
        if category is not None:
            self._record(category, primitive)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Record hook replacements and factory-derived boundary owners."""

        for target in node.targets:
            self._record_hook_target(target)
            self._record_factory_binding(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Record annotated hook replacements and factory-derived owners."""

        self._record_hook_target(node.target)
        if node.value is not None:
            self._record_factory_binding(node.target, node.value)
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        """Record explicit SystemExit as a process termination boundary."""

        exception = node.exc
        if isinstance(exception, ast.Call):
            exception = exception.func
        if exception is not None and self._resolved_name(exception) in {
            "SystemExit",
            "builtins.SystemExit",
        }:
            self._record("hard_exit", "builtins.SystemExit")
        self.generic_visit(node)

    def _record_hook_target(self, target: ast.expr) -> None:
        """Record one assignment when it replaces an authoritative hook."""

        primitive = self._resolved_name(target)
        category = _HOOK_TARGETS.get(primitive)
        if category is not None:
            self._record(category, primitive)

    def _record_factory_binding(self, target: ast.expr, value: ast.expr) -> None:
        """Retain a known factory result for later method-call classification."""

        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            return
        result_type = _FACTORY_RESULT_TYPES.get(self._resolved_name(value.func))
        if result_type is not None:
            self._bindings[-1][target.id] = result_type

    def _visit_owned(self, node: ast.AST, name: str) -> None:
        """Visit one definition with a stable dotted owner name."""

        self._owners.append(name)
        self._bindings.append({})
        self.generic_visit(node)
        self._bindings.pop()
        self._owners.pop()

    def _record(self, category: str, primitive: str) -> None:
        """Add one stable site without depending on source line numbers."""

        owner = ".".join(self._owners) or "<module>"
        count_key = (category, owner, primitive)
        occurrence = self._occurrences.get(count_key, 0) + 1
        self._occurrences[count_key] = occurrence
        self.sites.add(
            CrashBoundarySite(category, self._path, owner, primitive, occurrence)
        )

    def _resolved_name(self, expression: ast.expr) -> str:
        """Resolve a directly imported or attribute-qualified expression."""

        if isinstance(expression, ast.Name):
            for bindings in reversed(self._bindings):
                if expression.id in bindings:
                    return bindings[expression.id]
            return self._aliases.get(expression.id, expression.id)
        if isinstance(expression, ast.Attribute):
            owner = self._resolved_name(expression.value)
            return f"{owner}.{expression.attr}" if owner else expression.attr
        if isinstance(expression, ast.Call):
            return _FACTORY_RESULT_TYPES.get(
                self._resolved_name(expression.func),
                "",
            )
        return ""


__all__ = [
    "CrashBoundarySite",
    "discover_crash_boundary_sites",
    "validate_crash_boundary_inventory",
    "validate_crash_boundary_policy",
]
