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

"""Bootstrap the bundled production audit on Qt's offscreen platform."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import urllib.request
from collections import Counter
from collections.abc import Mapping
from ctypes import wintypes
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.bundled_comfy_workflow_rendering_harness import WorkflowAuditResult


def _configure_offscreen_environment() -> None:
    """Set fail-closed Qt variables before any PySide6 module can load."""

    imported_qt_modules = [
        module_name
        for module_name in sys.modules
        if module_name == "PySide6" or module_name.startswith("PySide6.")
    ]
    if imported_qt_modules:
        raise RuntimeError(
            "Refusing audit because PySide6 loaded before offscreen bootstrap."
        )
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_OPENGL"] = "software"
    os.environ["SUGARSUBSTITUTE_HEADLESS_TEST"] = "1"


def _lower_process_priority() -> None:
    """Run the Windows audit process below normal interactive priority."""

    if os.name != "nt":
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_current_process = cast_any(kernel32.GetCurrentProcess)
    set_priority_class = cast_any(kernel32.SetPriorityClass)
    get_current_process.argtypes = []
    get_current_process.restype = wintypes.HANDLE
    set_priority_class.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    set_priority_class.restype = wintypes.BOOL
    below_normal_priority_class = 0x00004000
    process_handle = get_current_process()
    if not set_priority_class(process_handle, below_normal_priority_class):
        error_code = ctypes.get_last_error()
        raise OSError(error_code, "Failed to set below-normal audit priority.")


def cast_any(value: object) -> Any:
    """Return a dynamically loaded Win32 symbol for strict typing boundaries."""

    return value


def _load_object_info(url: str) -> dict[str, Mapping[str, object]]:
    """Load and validate the live Comfy node-definition catalog."""

    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        payload = json.load(response)
    if not isinstance(payload, Mapping):
        raise ValueError("Comfy object_info response is not a mapping.")
    return {
        str(class_type): definition
        for class_type, definition in payload.items()
        if isinstance(definition, Mapping)
    }


class _ProgressReporter:
    """Publish progress to stdout and an independently monitorable artifact."""

    def __init__(self, path: Path) -> None:
        """Initialize an empty progress artifact for one corpus run."""

        self._path = path.resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text("", encoding="utf-8")

    def __call__(
        self,
        completed: int,
        total: int,
        result: WorkflowAuditResult,
    ) -> None:
        """Append one flush-safe observational progress row."""

        status = "PASS" if result.succeeded else f"FAIL:{len(result.findings)}"
        finding_codes = Counter(finding.code for finding in result.findings)
        code_summary = ",".join(
            f"{code}:{count}" for code, count in sorted(finding_codes.items())
        )
        line = (
            f"{completed}/{total}|{status}|{result.workflow}|"
            f"nodes={result.converted_node_count}|cards={result.built_card_count}|"
            f"fields={result.registered_field_widget_count}|"
            f"ms={result.elapsed_ms:.1f}|codes={code_summary}"
        )
        print(line, flush=True)  # noqa: T201
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(f"{line}\n")


def _write_probe(path: Path, result: WorkflowAuditResult, qt_platform: str) -> None:
    """Persist the offscreen proof and one-workflow production observation."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "audit_mode": "passive_production_observation_probe",
                "qt_platform": qt_platform,
                "result": asdict(result),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def main() -> int:
    """Bootstrap offscreen Qt, prove it, then run the requested audit scope."""

    _configure_offscreen_environment()
    _lower_process_priority()
    from PySide6.QtWidgets import QApplication

    from tests.bundled_comfy_workflow_rendering_harness import (
        BundledComfyWorkflowRenderingHarness,
    )

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    if app.platformName().casefold() != "offscreen":
        raise RuntimeError(
            f"Refusing audit on interactive Qt platform {app.platformName()!r}."
        )

    parser = argparse.ArgumentParser()
    parser.add_argument("template_root", type=Path)
    parser.add_argument(
        "--object-info-url", default="http://127.0.0.1:8188/object_info"
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("build/test-results/bundled-workflow-production-audit"),
    )
    parser.add_argument("--shell-batch-size", type=int, default=25)
    parser.add_argument("--workflow-timeout-ms", type=int, default=30_000)
    parser.add_argument("--progress-log", type=Path)
    parser.add_argument("--probe-workflow", default="default")
    parser.add_argument("--probe-only", action="store_true")
    args = parser.parse_args()
    definitions = _load_object_info(args.object_info_url)
    probe_harness = BundledComfyWorkflowRenderingHarness(
        template_root=args.template_root,
        node_definitions=definitions,
        artifact_root=args.artifact_root / "probe",
        shell_batch_size=1,
        workflow_timeout_ms=args.workflow_timeout_ms,
    )
    probe_result = probe_harness.run_probe(args.probe_workflow)
    qt_platform = app.platformName()
    if qt_platform.casefold() != "offscreen":
        raise RuntimeError(f"Offscreen probe used unexpected platform {qt_platform!r}.")
    _write_probe(args.artifact_root / "offscreen-probe.json", probe_result, qt_platform)
    print(  # noqa: T201
        f"PROBE|workflow={probe_result.workflow}|platform={qt_platform}|"
        f"findings={len(probe_result.findings)}",
        flush=True,
    )
    if args.probe_only:
        return 0
    progress_log = args.progress_log or args.artifact_root / "progress.log"
    harness = BundledComfyWorkflowRenderingHarness(
        template_root=args.template_root,
        node_definitions=definitions,
        artifact_root=args.artifact_root,
        shell_batch_size=args.shell_batch_size,
        workflow_timeout_ms=args.workflow_timeout_ms,
        progress_callback=_ProgressReporter(progress_log),
    )
    report = harness.run()
    print(  # noqa: T201
        "SUMMARY|"
        f"workflows={report.workflow_count}|"
        f"passed={report.succeeded_workflow_count}|"
        f"failed={report.failed_workflow_count}|"
        f"findings={report.finding_count}|"
        f"report={args.artifact_root.resolve() / 'report.json'}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
