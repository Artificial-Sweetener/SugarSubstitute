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

"""Own replayable diagnostic artifacts for real-shell prompt-editor evidence."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import json
from pathlib import Path
import platform
import sys

from PySide6 import QtCore
from PySide6.QtGui import QGuiApplication

from substitute.application.ports import PromptAutocompleteSuggestion
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorAbuseFinding,
    PromptEditorStateSnapshot,
    PromptEditorTrace,
)
from tests.support.prompt_editor.real_shell.snapshot_serialization import (
    write_snapshot_json,
)


class PromptEditorArtifactStore:
    """Persist owner-attributed snapshots, traces, and replay context."""

    def __init__(
        self,
        artifact_root: Path,
        *,
        active_workflow_id_provider: Callable[[], str | None],
        trace_provider: Callable[[], PromptEditorTrace],
        autocomplete_results: Mapping[str, tuple[PromptAutocompleteSuggestion, ...]],
    ) -> None:
        """Capture immutable artifact context for one mounted harness session."""

        self._artifact_root = artifact_root
        self._active_workflow_id_provider = active_workflow_id_provider
        self._trace_provider = trace_provider
        self._autocomplete_fixtures = {
            prefix: [suggestion.tag for suggestion in suggestions]
            for prefix, suggestions in autocomplete_results.items()
        }

    def save(
        self,
        name: str,
        *,
        before: PromptEditorStateSnapshot,
        after: PromptEditorStateSnapshot,
        invariant: str,
        observed: str,
    ) -> Path:
        """Persist one failure's snapshots, metadata, trace, and replay guide."""

        directory = self._artifact_root / name
        directory.mkdir(parents=True, exist_ok=True)
        write_snapshot_json(directory / "state-before.json", before)
        write_snapshot_json(directory / "state-after.json", after)
        self._write_metadata_json(directory / "metadata.json", after)
        self._write_trace_json(directory / "trace.json", self._trace_provider())
        (directory / "README.md").write_text(
            "\n".join(
                (
                    f"# {name}",
                    "",
                    f"Invariant: {invariant}",
                    "",
                    f"Observed: {observed}",
                    "",
                    "Replay command:",
                    (
                        ".\\.venv\\Scripts\\python.exe -m pytest "
                        "tests\\qualification\\prompt_editor\\real_shell -q"
                    ),
                    "",
                    "Likely owner path: real-shell harness diagnostic pending.",
                    "",
                )
            ),
            encoding="utf-8",
        )
        return directory

    def _write_metadata_json(
        self,
        path: Path,
        snapshot: PromptEditorStateSnapshot,
    ) -> None:
        """Write environment and mounted-shell metadata for replay diagnostics."""

        screen = QGuiApplication.primaryScreen()
        metadata = {
            "python": sys.version,
            "qt_version": QtCore.qVersion(),
            "qt_platform": QGuiApplication.platformName(),
            "os": platform.platform(),
            "screen_device_pixel_ratio": None
            if screen is None
            else screen.devicePixelRatio(),
            "shell_size": snapshot.geometries.get("shell"),
            "editor_panel_size": snapshot.geometries.get("panel"),
            "editor_viewport_size": snapshot.geometries.get("viewport"),
            "active_workflow_id": self._active_workflow_id_provider(),
            "autocomplete_fixtures": self._autocomplete_fixtures,
        }
        path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )

    @staticmethod
    def _write_trace_json(path: Path, trace: PromptEditorTrace) -> None:
        """Write one replay trace JSON file."""

        payload = {
            "seed": trace.seed,
            "actions": [
                {
                    "kind": action.kind,
                    "value": action.value,
                    "key": action.key,
                    "modifiers": action.modifiers,
                }
                for action in trace.actions
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def group_abuse_findings(
    findings: Sequence[PromptEditorAbuseFinding],
) -> dict[str, tuple[str, ...]]:
    """Group abuse failures by visible symptom, then owner hypothesis."""

    grouped: dict[str, set[str]] = {}
    for finding in findings:
        grouped.setdefault(finding.symptom, set()).add(finding.owner_hypothesis)
    return {
        symptom: tuple(sorted(owner_hypotheses))
        for symptom, owner_hypotheses in sorted(grouped.items())
    }


def owner_hypothesis_for_violation(violation: str) -> str:
    """Map one invariant failure to the first likely production owner."""

    if "tab" in violation or "control_character" in violation:
        return "prompt editor keymap/interactions"
    if "autocomplete" in violation or "session" in violation or "popup" in violation:
        return "autocomplete lifecycle/session owner"
    if "caret" in violation or "cursor" in violation:
        return "projection source-to-visual caret-map owner"
    if "geometry_shift" in violation:
        return "prompt editor sizing owner"
    if "visible_row_shift" in violation or "visible_fragment_shift" in violation:
        return "projection layout, paint cache, or editor sizing owner"
    if "projection" in violation or "document_view" in violation:
        return "projection source/change and repaint owner"
    if "selection" in violation:
        return "prompt editor selection owner"
    return "prompt editor event route/focus target"


def safe_artifact_name(value: str) -> str:
    """Return a Windows-safe artifact path component."""

    return "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in value
    ).strip("-")
