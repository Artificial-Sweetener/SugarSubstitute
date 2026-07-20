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

"""Guard the raw execution inventory during the execution-layer migration."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUBSTITUTE_ROOT = PROJECT_ROOT / "substitute"

LEGACY_EXECUTION_FILE_REASONS = {
    "substitute/infrastructure/comfy/posix_guardian_entry.py": (
        "external POSIX helper process cannot consume the app execution runtime; "
        "covered by tests/test_posix_guardian_containment.py"
    ),
}
LEGACY_EXECUTION_FILES = frozenset(LEGACY_EXECUTION_FILE_REASONS)

EXECUTION_ADAPTER_FILES = frozenset(
    {
        "substitute/app/bootstrap/execution_runtime.py",
        "substitute/infrastructure/execution/long_lived_task.py",
        "substitute/infrastructure/execution/parallel_map.py",
        "substitute/infrastructure/execution/process_output.py",
        "substitute/infrastructure/execution/thread_pool_lane.py",
        "substitute/application/execution/cancellation.py",
        "substitute/application/execution/policies.py",
        "substitute/application/execution/task_scope.py",
        "substitute/presentation/editor/prompt_editor/async_work/task_executor.py",
    }
)
EXECUTION_LANE_FACTORY_FILES = frozenset(
    {
        "substitute/app/bootstrap/execution_runtime.py",
    }
)
EXECUTION_LANE_CONSTRUCTORS = frozenset(
    {
        "ThreadPoolExecutionLane",
    }
)

DOCUMENTED_NON_EXECUTION_FILES = {
    "substitute/app/bootstrap/launch_splash.py": frozenset({"threading.Lock"}),
    "substitute/app/bootstrap/lifecycle.py": frozenset({"threading.Lock"}),
    "substitute/app/bootstrap/startup_shutdown.py": frozenset({"threading.Lock"}),
    "substitute/app/bootstrap/workspace_restore_asset_preload.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/cube_library/update_coordinator.py": frozenset(
        {"threading.Lock"}
    ),
    "substitute/application/cubes/cube_load_service.py": frozenset({"threading.Lock"}),
    "substitute/application/localization/comfy_node_catalog_store.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/model_metadata/model_catalog_service.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/model_metadata/model_choice_catalog_index.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/model_metadata/rich_choice_resolver.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/model_metadata/scoped_metadata_refresh_service.py": (
        frozenset({"threading.RLock"})
    ),
    "substitute/application/prompt_editor/prompt_document_cache.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/prompt_editor/prompt_lora_catalog_service.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/prompt_editor/prompt_syntax_service.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/application/recipes/model_hash_lookup.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/infrastructure/comfy/managed_launcher.py": frozenset(
        {"threading.Lock"}
    ),
    "substitute/infrastructure/external/comfy_object_info_client.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/infrastructure/localization/comfy_i18n_client.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/infrastructure/persistence/file_prompt_autocomplete_gateway.py": (
        frozenset({"threading.RLock"})
    ),
    "substitute/infrastructure/persistence/configured_prompt_autocomplete_gateway.py": (
        frozenset({"threading.RLock"})
    ),
    "substitute/infrastructure/persistence/image_naming.py": frozenset(
        {"threading.Lock"}
    ),
    "substitute/presentation/shell/model_catalog_update_bridge.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/presentation/shell/model_metadata_update_bridge.py": frozenset(
        {"threading.RLock"}
    ),
    "substitute/presentation/shell/model_metadata_context_action_handler.py": (
        frozenset({"threading.RLock"})
    ),
    "substitute/presentation/cube_picker/cube_stack_cart_modal.py": frozenset(
        {"QEventLoop"}
    ),
    "substitute/shared/qpane_sam_warmup_state.py": frozenset({"threading.Lock"}),
    "substitute/shared/startup_trace.py": frozenset({"threading.RLock"}),
}

NEVER_CANCELLED_FILE_REASONS: dict[str, str] = {}
LONG_LIVED_HANDLE_CONSTRUCTOR_FILES = {
    "substitute/app/bootstrap/execution_runtime.py": (
        "main process runtime owns long-lived task start and registration"
    ),
    "substitute/app/bootstrap/standalone_long_lived_execution.py": (
        "explicit standalone owner for pre-runtime and helper-process boundaries"
    ),
}
WORKER_TERMINOLOGY_FILE_REASONS = {
    "substitute/app/bootstrap/execution_runtime.py": (
        "runtime lane configuration maps logical lanes to concrete thread pools"
    ),
    "substitute/infrastructure/execution/thread_pool_lane.py": (
        "concrete thread-pool adapter owns worker-thread implementation details"
    ),
    "substitute/infrastructure/execution/parallel_map.py": (
        "bounded parallel-map adapter owns thread-pool implementation details"
    ),
    "substitute/application/node_behavior/__init__.py": (
        "exports Comfy sampler_worker domain-role inference"
    ),
    "substitute/domain/node_behavior/__init__.py": (
        "exports Comfy sampler_worker domain-role inference"
    ),
    "substitute/domain/node_behavior/inference.py": (
        "models Comfy sampler_worker as node behavior domain terminology"
    ),
    "substitute/domain/node_behavior/models.py": (
        "models Comfy sampler_worker as node behavior domain terminology"
    ),
}
WORKER_TERMINOLOGY_TERMS = (
    "worker",
    "Worker",
    "WORKER",
    "thread_name_prefix",
)
PROMPT_PRESENTATION_EXECUTION_BOUNDARY_ROOTS = (
    SUBSTITUTE_ROOT / "presentation" / "editor",
    SUBSTITUTE_ROOT / "presentation" / "managed_text_assets",
)
PROMPT_PRESENTATION_EXECUTION_BOUNDARY_FILES = (
    SUBSTITUTE_ROOT / "presentation" / "shell" / "workflow_ui_factory.py",
)
PROMPT_PRESENTATION_QT_DISPATCHER_FILES = frozenset(
    {
        "substitute/presentation/editor/prompt_editor/async_work/main_thread_dispatcher.py",
    }
)
PROMPT_PRESENTATION_RUNTIME_TERMS = (
    "execution_runtime",
    "ExecutionRuntime(",
    ".submitter(",
)

PURE_LAYER_ROOTS = (
    SUBSTITUTE_ROOT / "domain",
    SUBSTITUTE_ROOT / "application",
)
FORBIDDEN_QT_EXECUTION_IMPORT = "substitute.presentation.qt.execution"

RAW_EXECUTION_IMPORTS = {
    "threading.Condition": "threading.Condition",
    "threading.Event": "threading.Event",
    "threading.Lock": "threading.Lock",
    "threading.RLock": "threading.RLock",
    "threading.Thread": "threading.Thread",
    "concurrent.futures.ThreadPoolExecutor": "ThreadPoolExecutor",
    "PySide6.QtCore.QEventLoop": "QEventLoop",
    "PySide6.QtCore.QRunnable": "QRunnable",
    "PySide6.QtCore.QThreadPool": "QThreadPool",
}


def _python_files(root: Path) -> tuple[Path, ...]:
    """Return Python source files below one root."""

    return tuple(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _relative_path(path: Path) -> str:
    """Return one repository-relative path using POSIX separators."""

    return path.relative_to(PROJECT_ROOT).as_posix()


def _call_name(node: ast.AST) -> str:
    """Return a dotted call name from an AST call target."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def _resolved_name(name: str, aliases: dict[str, str]) -> str:
    """Return a dotted name with its leading import alias expanded."""

    head, separator, tail = name.partition(".")
    resolved_head = aliases.get(head, head)
    if not separator:
        return resolved_head
    return f"{resolved_head}.{tail}"


def _base_name(node: ast.AST) -> str:
    """Return a dotted class base name."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _base_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    return ""


def _raw_execution_findings(source_path: Path) -> tuple[str, ...]:
    """Return raw execution primitives used in one source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    aliases = _raw_execution_aliases(tree)
    findings: set[str] = set()
    qevent_loop_names = _qevent_loop_variable_names(tree, aliases=aliases)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = _resolved_name(_call_name(node.func), aliases)
            raw_call_name = RAW_EXECUTION_IMPORTS.get(call_name, call_name)
            if raw_call_name == "ThreadPoolExecutor":
                findings.add("ThreadPoolExecutor")
            if raw_call_name == "threading.Thread":
                findings.add("threading.Thread")
            if raw_call_name == "QThreadPool":
                findings.add("QThreadPool")
            if call_name.endswith("QThreadPool.globalInstance.start"):
                findings.add("QThreadPool.globalInstance().start")
            if raw_call_name == "QEventLoop":
                findings.add("QEventLoop")
            if _is_qevent_loop_exec(node, qevent_loop_names=qevent_loop_names):
                findings.add("QEventLoop.exec")
            if raw_call_name in {
                "threading.Condition",
                "threading.Event",
                "threading.Lock",
                "threading.RLock",
            }:
                findings.add(raw_call_name)
        elif isinstance(node, ast.ClassDef):
            if any(
                RAW_EXECUTION_IMPORTS.get(
                    _resolved_name(_base_name(base), aliases),
                    _resolved_name(_base_name(base), aliases),
                )
                == "QRunnable"
                for base in node.bases
            ):
                findings.add("QRunnable")
        elif isinstance(node, ast.keyword) and node.arg == "default_factory":
            factory_name = _resolved_name(_call_name(node.value), aliases)
            raw_factory_name = RAW_EXECUTION_IMPORTS.get(factory_name, factory_name)
            if raw_factory_name in {
                "threading.Condition",
                "threading.Event",
                "threading.Lock",
                "threading.RLock",
            }:
                findings.add(raw_factory_name)
    return tuple(sorted(findings))


def _raw_execution_aliases(tree: ast.AST) -> dict[str, str]:
    """Return import aliases that can hide raw execution primitives."""

    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"threading", "concurrent.futures"}:
                    aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                imported_name = f"{node.module}.{alias.name}"
                if imported_name in RAW_EXECUTION_IMPORTS:
                    aliases[alias.asname or alias.name] = imported_name
    return aliases


def _never_cancelled_findings(source_path: Path) -> tuple[int, ...]:
    """Return line numbers where production code creates a never-cancelled token."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    aliases = _never_cancelled_aliases(tree)
    line_numbers: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _resolved_name(_call_name(node.func), aliases)
        if call_name.endswith("NeverCancelled"):
            line_numbers.append(node.lineno)
    return tuple(sorted(line_numbers))


def _never_cancelled_aliases(tree: ast.AST) -> dict[str, str]:
    """Return import aliases that can hide NeverCancelled construction."""

    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                if alias.name != "NeverCancelled":
                    continue
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("substitute.application.execution"):
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _production_wait_for_idle_findings(source_path: Path) -> tuple[int, ...]:
    """Return production wait helpers that pump events or sleep."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    line_numbers: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "wait_for_idle":
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            call_name = _call_name(child.func)
            if call_name.endswith("processEvents") or call_name in {
                "sleep",
                "time.sleep",
            }:
                line_numbers.append(node.lineno)
                break
    return tuple(line_numbers)


def _qevent_loop_variable_names(
    tree: ast.AST,
    *,
    aliases: dict[str, str],
) -> set[str]:
    """Return local names assigned from QEventLoop construction."""

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        call_name = _resolved_name(_call_name(node.value.func), aliases)
        if RAW_EXECUTION_IMPORTS.get(call_name, call_name) != "QEventLoop":
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _is_qevent_loop_exec(
    node: ast.Call,
    *,
    qevent_loop_names: set[str],
) -> bool:
    """Return whether one call is exec() on a known QEventLoop instance."""

    if not isinstance(node.func, ast.Attribute) or node.func.attr != "exec":
        return False
    value = node.func.value
    if isinstance(value, ast.Name):
        return value.id in qevent_loop_names
    if isinstance(value, ast.Call):
        return _call_name(value.func).endswith("QEventLoop")
    return False


def _module_level_executor_findings(source_path: Path) -> tuple[int, ...]:
    """Return line numbers where module-level ThreadPoolExecutor is constructed."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    line_numbers: list[int] = []
    for statement in tree.body:
        for node in ast.walk(statement):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node.func).endswith("ThreadPoolExecutor"):
                line_numbers.append(node.lineno)
    return tuple(line_numbers)


def _execution_lane_constructor_findings(
    source_path: Path,
) -> tuple[tuple[int, str], ...]:
    """Return line numbers where concrete execution lanes are constructed."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node.func)
        if any(
            call_name == constructor or call_name.endswith(f".{constructor}")
            for constructor in EXECUTION_LANE_CONSTRUCTORS
        ):
            findings.append((node.lineno, call_name))
    return tuple(findings)


def _long_lived_handle_constructor_findings(
    source_path: Path,
) -> tuple[tuple[int, str], ...]:
    """Return lines where production code constructs long-lived task handles."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node.func)
        if call_name == "LongLivedTaskHandle" or call_name.endswith(
            ".LongLivedTaskHandle"
        ):
            findings.append((node.lineno, call_name))
    return tuple(findings)


def _worker_terminology_findings(source_path: Path) -> tuple[tuple[int, str], ...]:
    """Return production lines that still use worker/thread-pool vocabulary."""

    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(
        source_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line_terms = tuple(term for term in WORKER_TERMINOLOGY_TERMS if term in line)
        findings.extend((line_number, term) for term in line_terms)
    return tuple(findings)


def _prompt_presentation_runtime_findings(
    source_path: Path,
) -> tuple[tuple[int, str], ...]:
    """Return reusable editor-presentation runtime ownership leaks."""

    relative = _relative_path(source_path)
    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(
        source_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        findings.extend(
            (line_number, term)
            for term in PROMPT_PRESENTATION_RUNTIME_TERMS
            if term in line
        )
        if (
            relative not in PROMPT_PRESENTATION_QT_DISPATCHER_FILES
            and "QtOwnerThreadDispatcher" in line
        ):
            findings.append((line_number, "QtOwnerThreadDispatcher"))
    return tuple(findings)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return imported module names from one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_raw_execution_sites_stay_inside_legacy_inventory() -> None:
    """Prevent new raw worker/thread/pool sites during phased migration."""

    violations: dict[str, tuple[str, ...]] = {}
    unexpected_non_execution: dict[str, tuple[str, ...]] = {}
    for source_path in _python_files(SUBSTITUTE_ROOT):
        findings = _raw_execution_findings(source_path)
        if not findings:
            continue
        relative = _relative_path(source_path)
        if relative in LEGACY_EXECUTION_FILES or relative in EXECUTION_ADAPTER_FILES:
            continue
        allowed_findings = DOCUMENTED_NON_EXECUTION_FILES.get(relative)
        if allowed_findings is not None:
            extra_findings = tuple(
                finding for finding in findings if finding not in allowed_findings
            )
            if extra_findings:
                unexpected_non_execution[relative] = extra_findings
            continue
        violations[relative] = findings

    assert violations == {}
    assert unexpected_non_execution == {}


def test_legacy_execution_inventory_documents_each_remaining_exception() -> None:
    """Require every raw-execution exception to carry an owning reason."""

    assert set(LEGACY_EXECUTION_FILE_REASONS) == set(LEGACY_EXECUTION_FILES)
    assert all(reason.strip() for reason in LEGACY_EXECUTION_FILE_REASONS.values())


def test_module_level_executors_stay_inside_legacy_inventory() -> None:
    """Prevent new module-level executor singletons."""

    violations: dict[str, tuple[int, ...]] = {}
    for source_path in _python_files(SUBSTITUTE_ROOT):
        line_numbers = _module_level_executor_findings(source_path)
        if not line_numbers:
            continue
        relative = _relative_path(source_path)
        if (
            relative not in LEGACY_EXECUTION_FILES
            and relative not in EXECUTION_ADAPTER_FILES
        ):
            violations[relative] = line_numbers

    assert violations == {}


def test_execution_lanes_are_constructed_only_by_runtime_factories() -> None:
    """Keep concrete lane ownership inside app execution composition."""

    violations: dict[str, tuple[tuple[int, str], ...]] = {}
    for source_path in _python_files(SUBSTITUTE_ROOT):
        findings = _execution_lane_constructor_findings(source_path)
        if not findings:
            continue
        relative = _relative_path(source_path)
        if relative in EXECUTION_LANE_FACTORY_FILES:
            continue
        violations[relative] = findings

    assert violations == {}


def test_long_lived_handles_start_only_inside_runtime_or_explicit_early_owners() -> (
    None
):
    """Prevent feature code from starting long-lived handles before registration."""

    violations: dict[str, tuple[tuple[int, str], ...]] = {}
    for source_path in _python_files(SUBSTITUTE_ROOT):
        findings = _long_lived_handle_constructor_findings(source_path)
        if not findings:
            continue
        relative = _relative_path(source_path)
        if relative in LONG_LIVED_HANDLE_CONSTRUCTOR_FILES:
            continue
        violations[relative] = findings

    assert violations == {}
    assert all(
        reason.strip() for reason in LONG_LIVED_HANDLE_CONSTRUCTOR_FILES.values()
    )


def test_worker_terminology_stays_inside_execution_or_domain_role_owners() -> None:
    """Keep feature code from reintroducing local worker/executor language."""

    violations: dict[str, tuple[tuple[int, str], ...]] = {}
    files_with_findings: set[str] = set()
    for source_path in _python_files(SUBSTITUTE_ROOT):
        findings = _worker_terminology_findings(source_path)
        if not findings:
            continue
        relative = _relative_path(source_path)
        files_with_findings.add(relative)
        if relative not in WORKER_TERMINOLOGY_FILE_REASONS:
            violations[relative] = findings

    assert violations == {}
    assert files_with_findings == set(WORKER_TERMINOLOGY_FILE_REASONS)
    assert all(reason.strip() for reason in WORKER_TERMINOLOGY_FILE_REASONS.values())


def test_prompt_editor_has_no_legacy_worker_execution_terms() -> None:
    """Prevent removed prompt-owned worker terminology from returning."""

    prompt_editor_root = SUBSTITUTE_ROOT / "presentation" / "editor" / "prompt_editor"
    prompt_test_root = PROJECT_ROOT / "tests"
    panel_lora_refresh = (
        SUBSTITUTE_ROOT
        / "presentation"
        / "editor"
        / "panel"
        / "lora_metadata_refresh_controller.py"
    )
    violations: dict[str, tuple[str, ...]] = {}
    forbidden_terms = (
        "worker",
        "Worker",
        "WORKER",
        "worker_pool",
        "WorkerPool",
        "PromptEditorWorkerPoolExecutor",
        "local executor",
        "fallback executor",
        "prompt-local lane",
        "local lane",
    )
    prompt_test_files = tuple(
        path
        for path in _python_files(prompt_test_root)
        if path.name.startswith("test_prompt")
        or path.name.startswith("prompt_")
        or path.name == "test_panel_lora_metadata_refresh_controller.py"
    )
    for source_path in (
        *_python_files(prompt_editor_root),
        panel_lora_refresh,
        *prompt_test_files,
    ):
        text = source_path.read_text(encoding="utf-8")
        findings = tuple(
            term
            for term in forbidden_terms
            if term in _prompt_execution_guardrail_text(text)
        )
        if findings:
            violations[_relative_path(source_path)] = findings

    assert violations == {}


def test_reusable_prompt_presentation_does_not_own_runtime_wiring() -> None:
    """Keep prompt/editor widgets behind composition-owned execution ports."""

    source_paths = [
        *(
            path
            for root in PROMPT_PRESENTATION_EXECUTION_BOUNDARY_ROOTS
            for path in _python_files(root)
        ),
        *PROMPT_PRESENTATION_EXECUTION_BOUNDARY_FILES,
    ]
    violations: dict[str, tuple[tuple[int, str], ...]] = {}
    for source_path in source_paths:
        findings = _prompt_presentation_runtime_findings(source_path)
        if findings:
            violations[_relative_path(source_path)] = findings

    assert violations == {}


def _prompt_execution_guardrail_text(text: str) -> str:
    """Return text with unrelated pytest xdist worker markers ignored."""

    ignored_fragments = (
        "PYTEST_XDIST_WORKER",
        "xdist worker",
        "xdist workers",
        "Windows xdist workers",
    )
    filtered_lines: list[str] = []
    for line in text.splitlines():
        if any(fragment in line for fragment in ignored_fragments):
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def test_pure_layers_do_not_import_qt_execution_adapters() -> None:
    """Keep future Qt execution adapters out of domain and application code."""

    violations: dict[str, tuple[str, ...]] = {}
    for root in PURE_LAYER_ROOTS:
        for source_path in _python_files(root):
            forbidden_imports = tuple(
                sorted(
                    module_name
                    for module_name in _imported_module_names(source_path)
                    if module_name.startswith(FORBIDDEN_QT_EXECUTION_IMPORT)
                )
            )
            if forbidden_imports:
                violations[_relative_path(source_path)] = forbidden_imports

    assert violations == {}


def test_never_cancelled_sites_stay_inside_documented_inventory() -> None:
    """Keep lifetime-less execution submissions visible during cleanup."""

    violations: dict[str, tuple[int, ...]] = {}
    for source_path in _python_files(SUBSTITUTE_ROOT):
        line_numbers = _never_cancelled_findings(source_path)
        if not line_numbers:
            continue
        relative = _relative_path(source_path)
        if relative not in NEVER_CANCELLED_FILE_REASONS:
            violations[relative] = line_numbers

    assert violations == {}


def test_never_cancelled_inventory_matches_current_source() -> None:
    """Require the NeverCancelled inventory to shrink as cleanup removes sites."""

    files_with_findings = {
        _relative_path(source_path)
        for source_path in _python_files(SUBSTITUTE_ROOT)
        if _never_cancelled_findings(source_path)
    }

    assert files_with_findings == set(NEVER_CANCELLED_FILE_REASONS)
    assert all(reason.strip() for reason in NEVER_CANCELLED_FILE_REASONS.values())


def test_production_wait_for_idle_does_not_pump_events_or_sleep() -> None:
    """Keep test event-pumping loops out of production classes."""

    violations: dict[str, tuple[int, ...]] = {}
    for source_path in _python_files(SUBSTITUTE_ROOT):
        findings = _production_wait_for_idle_findings(source_path)
        if findings:
            violations[_relative_path(source_path)] = findings

    assert violations == {}


def test_guardrail_inventory_matches_current_source() -> None:
    """Make inventory drift explicit when migration phases remove legacy sites."""

    files_with_findings = {
        _relative_path(source_path)
        for source_path in _python_files(SUBSTITUTE_ROOT)
        if _raw_execution_findings(source_path)
    }
    expected_files = (
        LEGACY_EXECUTION_FILES
        | EXECUTION_ADAPTER_FILES
        | set(DOCUMENTED_NON_EXECUTION_FILES)
    )

    assert files_with_findings == expected_files
