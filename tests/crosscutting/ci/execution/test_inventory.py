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

"""Guard the source execution inventory and its architectural boundaries."""

from __future__ import annotations

from pathlib import Path

from tests.crosscutting.ci.execution.inventory_policy import (
    DOCUMENTED_NON_EXECUTION_FILES,
    EXECUTION_ADAPTER_FILES,
    EXECUTION_LANE_CONSTRUCTORS,
    EXECUTION_LANE_FACTORY_FILES,
    FORBIDDEN_QT_EXECUTION_IMPORT,
    LEGACY_EXECUTION_FILE_REASONS,
    LEGACY_EXECUTION_FILES,
    LONG_LIVED_HANDLE_CONSTRUCTOR_FILES,
    NEVER_CANCELLED_FILE_REASONS,
    PROJECT_ROOT,
    PROMPT_PRESENTATION_EXECUTION_BOUNDARY_FILES,
    PROMPT_PRESENTATION_EXECUTION_BOUNDARY_ROOTS,
    PROMPT_PRESENTATION_QT_DISPATCHER_FILES,
    PROMPT_PRESENTATION_RUNTIME_TERMS,
    PURE_LAYER_ROOTS,
    RAW_EXECUTION_IMPORTS,
    SUBSTITUTE_ROOT,
    WORKER_TERMINOLOGY_FILE_REASONS,
    WORKER_TERMINOLOGY_TERMS,
)
from tests.crosscutting.ci.execution.inventory_scanner import ExecutionSourceScanner


def _python_files(root: Path) -> tuple[Path, ...]:
    """Return Python source files below one root."""

    return tuple(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _relative_path(path: Path) -> str:
    """Return one repository-relative path using POSIX separators."""

    return path.relative_to(PROJECT_ROOT).as_posix()


def _execution_inventory_state() -> dict[str, object]:
    """Return every governed execution finding from one source-tree pass."""

    raw_files: set[str] = set()
    raw_violations: dict[str, tuple[str, ...]] = {}
    documented_non_execution_drift: dict[str, tuple[str, ...]] = {}
    module_executor_violations: dict[str, tuple[int, ...]] = {}
    lane_constructor_violations: dict[str, tuple[tuple[int, str], ...]] = {}
    long_lived_handle_violations: dict[str, tuple[tuple[int, str], ...]] = {}
    terminology_files: set[str] = set()
    terminology_violations: dict[str, tuple[tuple[int, str], ...]] = {}
    never_cancelled_files: set[str] = set()
    never_cancelled_violations: dict[str, tuple[int, ...]] = {}
    wait_for_idle_violations: dict[str, tuple[int, ...]] = {}
    pure_layer_import_violations: dict[str, tuple[str, ...]] = {}

    for source_path in _python_files(SUBSTITUTE_ROOT):
        relative = _relative_path(source_path)
        scanner = ExecutionSourceScanner(source_path)

        raw_findings = scanner.raw_execution_findings(RAW_EXECUTION_IMPORTS)
        if raw_findings:
            raw_files.add(relative)
            if (
                relative not in LEGACY_EXECUTION_FILES
                and relative not in EXECUTION_ADAPTER_FILES
            ):
                allowed_findings = DOCUMENTED_NON_EXECUTION_FILES.get(relative)
                if allowed_findings is None:
                    raw_violations[relative] = raw_findings
                else:
                    extra_findings = tuple(
                        finding
                        for finding in raw_findings
                        if finding not in allowed_findings
                    )
                    if extra_findings:
                        documented_non_execution_drift[relative] = extra_findings

        executor_findings = scanner.module_level_executor_findings()
        if (
            executor_findings
            and relative not in LEGACY_EXECUTION_FILES
            and relative not in EXECUTION_ADAPTER_FILES
        ):
            module_executor_violations[relative] = executor_findings

        lane_findings = scanner.execution_lane_constructor_findings(
            EXECUTION_LANE_CONSTRUCTORS
        )
        if lane_findings and relative not in EXECUTION_LANE_FACTORY_FILES:
            lane_constructor_violations[relative] = lane_findings

        handle_findings = scanner.long_lived_handle_constructor_findings()
        if handle_findings and relative not in LONG_LIVED_HANDLE_CONSTRUCTOR_FILES:
            long_lived_handle_violations[relative] = handle_findings

        terminology_findings = scanner.terminology_findings(WORKER_TERMINOLOGY_TERMS)
        if terminology_findings:
            terminology_files.add(relative)
            if relative not in WORKER_TERMINOLOGY_FILE_REASONS:
                terminology_violations[relative] = terminology_findings

        never_cancelled_findings = scanner.never_cancelled_findings()
        if never_cancelled_findings:
            never_cancelled_files.add(relative)
            if relative not in NEVER_CANCELLED_FILE_REASONS:
                never_cancelled_violations[relative] = never_cancelled_findings

        wait_findings = scanner.production_wait_for_idle_findings()
        if wait_findings:
            wait_for_idle_violations[relative] = wait_findings

        if any(source_path.is_relative_to(root) for root in PURE_LAYER_ROOTS):
            forbidden_imports = tuple(
                sorted(
                    module_name
                    for module_name in scanner.imported_module_names()
                    if module_name.startswith(FORBIDDEN_QT_EXECUTION_IMPORT)
                )
            )
            if forbidden_imports:
                pure_layer_import_violations[relative] = forbidden_imports

    return {
        "documented_non_execution_drift": documented_non_execution_drift,
        "lane_constructor_violations": lane_constructor_violations,
        "long_lived_handle_violations": long_lived_handle_violations,
        "module_executor_violations": module_executor_violations,
        "never_cancelled_files": never_cancelled_files,
        "never_cancelled_violations": never_cancelled_violations,
        "pure_layer_import_violations": pure_layer_import_violations,
        "raw_execution_files": raw_files,
        "raw_execution_violations": raw_violations,
        "terminology_files": terminology_files,
        "terminology_violations": terminology_violations,
        "wait_for_idle_violations": wait_for_idle_violations,
    }


def _prompt_presentation_runtime_findings(
    source_path: Path,
) -> tuple[tuple[int, str], ...]:
    """Return reusable editor-presentation runtime ownership leaks."""

    relative = _relative_path(source_path)
    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(
        ExecutionSourceScanner(source_path).text.splitlines(), start=1
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


def _prompt_execution_guardrail_text(text: str) -> str:
    """Return text with unrelated pytest xdist worker markers ignored."""

    ignored_fragments = (
        "PYTEST_XDIST_WORKER",
        "xdist worker",
        "xdist workers",
        "Windows xdist workers",
    )
    return "\n".join(
        line
        for line in text.splitlines()
        if not any(fragment in line for fragment in ignored_fragments)
    )


def test_execution_source_inventory_matches_current_policy() -> None:
    """Keep all execution sources inside their exact architectural owners."""

    expected_state: dict[str, object] = {
        "documented_non_execution_drift": {},
        "lane_constructor_violations": {},
        "long_lived_handle_violations": {},
        "module_executor_violations": {},
        "never_cancelled_files": set(NEVER_CANCELLED_FILE_REASONS),
        "never_cancelled_violations": {},
        "pure_layer_import_violations": {},
        "raw_execution_files": LEGACY_EXECUTION_FILES
        | EXECUTION_ADAPTER_FILES
        | set(DOCUMENTED_NON_EXECUTION_FILES),
        "raw_execution_violations": {},
        "terminology_files": set(WORKER_TERMINOLOGY_FILE_REASONS),
        "terminology_violations": {},
        "wait_for_idle_violations": {},
    }

    assert _execution_inventory_state() == expected_state


def test_execution_inventory_records_document_each_exception() -> None:
    """Require every explicit execution exception to carry an owning reason."""

    assert set(LEGACY_EXECUTION_FILE_REASONS) == set(LEGACY_EXECUTION_FILES)
    assert all(reason.strip() for reason in LEGACY_EXECUTION_FILE_REASONS.values())
    assert all(reason.strip() for reason in NEVER_CANCELLED_FILE_REASONS.values())
    assert all(
        reason.strip() for reason in LONG_LIVED_HANDLE_CONSTRUCTOR_FILES.values()
    )
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
    violations: dict[str, tuple[str, ...]] = {}
    for source_path in (
        *_python_files(prompt_editor_root),
        panel_lora_refresh,
        *prompt_test_files,
    ):
        text = ExecutionSourceScanner(source_path).text
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
    violations = {
        _relative_path(source_path): findings
        for source_path in source_paths
        if (findings := _prompt_presentation_runtime_findings(source_path))
    }

    assert violations == {}
