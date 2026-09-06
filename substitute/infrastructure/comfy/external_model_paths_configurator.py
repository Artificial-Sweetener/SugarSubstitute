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

"""Persist one non-destructive WebUI library mapping in Comfy configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re

from substitute.infrastructure.comfy.webui_model_library_detector import (
    WebUiModelLibraryDetectionError,
    WebUiModelLibraryDetector,
)

_BEGIN_MARKER = "# BEGIN SUGARSUBSTITUTE CONNECTED WEBUI MODELS"
_END_MARKER = "# END SUGARSUBSTITUTE CONNECTED WEBUI MODELS"
_ROOT_PREFIX = "# models_root: "
_SECTION_NAME = "sugarsubstitute_connected_webui_models"
_OWNED_BLOCK_PATTERN = re.compile(
    rf"(?:\r?\n)?{re.escape(_BEGIN_MARKER)}\r?\n.*?\r?\n{re.escape(_END_MARKER)}(?:\r?\n)?",
    re.DOTALL,
)


class ExternalModelPathsConfigurationError(RuntimeError):
    """Report unsafe or malformed external-model configuration state."""


class ComfyExternalModelPathsConfigurator:
    """Own only SugarSubstitute's marked block in Comfy extra model paths."""

    def __init__(
        self,
        detector: WebUiModelLibraryDetector | None = None,
    ) -> None:
        """Store the detector used to resolve one selected models directory."""

        self._detector = detector or WebUiModelLibraryDetector()

    def configure(self, workspace: Path, models_root: Path | None) -> None:
        """Replace the owned mapping while preserving all user-authored YAML."""

        config_path = workspace.resolve(strict=False) / "extra_model_paths.yaml"
        existing = self._read_existing(config_path)
        without_owned_block, replacements = _OWNED_BLOCK_PATTERN.subn("\n", existing)
        if replacements > 1:
            raise ExternalModelPathsConfigurationError(
                "Comfy extra model paths contain multiple SugarSubstitute blocks."
            )
        if replacements == 0 and _section_is_present(existing):
            raise ExternalModelPathsConfigurationError(
                "Comfy extra model paths already use SugarSubstitute's reserved section."
            )
        if models_root is None:
            self._write_or_remove(config_path, _clean_remaining(without_owned_block))
            return
        try:
            library = self._detector.detect(models_root)
        except WebUiModelLibraryDetectionError:
            self._write_or_remove(config_path, _clean_remaining(without_owned_block))
            return
        updated = _append_owned_block(
            _clean_remaining(without_owned_block),
            _render_owned_block(library.models_root, library.paths_by_kind()),
        )
        self._write_atomic(config_path, updated)

    def load_models_root(self, workspace: Path) -> Path | None:
        """Return the selected root recorded in the owned block, when present."""

        config_path = workspace.resolve(strict=False) / "extra_model_paths.yaml"
        existing = self._read_existing(config_path)
        match = _OWNED_BLOCK_PATTERN.search(existing)
        if match is None:
            return None
        for line in match.group(0).splitlines():
            if not line.startswith(_ROOT_PREFIX):
                continue
            try:
                value = json.loads(line.removeprefix(_ROOT_PREFIX))
            except json.JSONDecodeError as error:
                raise ExternalModelPathsConfigurationError(
                    "SugarSubstitute's WebUI model-root record is malformed."
                ) from error
            if not isinstance(value, str) or not value.strip():
                raise ExternalModelPathsConfigurationError(
                    "SugarSubstitute's WebUI model-root record is invalid."
                )
            return Path(value).resolve(strict=False)
        raise ExternalModelPathsConfigurationError(
            "SugarSubstitute's WebUI model-root record is missing."
        )

    @staticmethod
    def _read_existing(config_path: Path) -> str:
        """Read existing configuration without creating its workspace."""

        try:
            return (
                config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
            )
        except OSError as error:
            raise ExternalModelPathsConfigurationError(
                "Comfy extra model paths could not be read."
            ) from error

    def _write_or_remove(self, config_path: Path, remaining: str) -> None:
        """Remove an app-only file or retain all remaining user content."""

        if remaining.strip():
            self._write_atomic(config_path, remaining)
            return
        try:
            config_path.unlink(missing_ok=True)
        except OSError as error:
            raise ExternalModelPathsConfigurationError(
                "Comfy extra model paths could not be removed."
            ) from error

    @staticmethod
    def _write_atomic(config_path: Path, content: str) -> None:
        """Atomically replace configuration after a complete local write."""

        config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = config_path.with_name(
            f".{config_path.name}.sugarsubstitute.tmp"
        )
        try:
            temporary_path.write_text(content, encoding="utf-8", newline="\n")
            os.replace(temporary_path, config_path)
        except OSError as error:
            temporary_path.unlink(missing_ok=True)
            raise ExternalModelPathsConfigurationError(
                "Comfy extra model paths could not be saved."
            ) from error


def _section_is_present(content: str) -> bool:
    """Return whether user-authored YAML already occupies the reserved key."""

    return re.search(rf"(?m)^\s*{re.escape(_SECTION_NAME)}\s*:", content) is not None


def _clean_remaining(content: str) -> str:
    """Normalize only whitespace left where the owned block was removed."""

    return content.strip("\r\n") + ("\n" if content.strip("\r\n") else "")


def _append_owned_block(content: str, block: str) -> str:
    """Append the owned mapping after preserved user configuration."""

    return f"{content.rstrip()}\n\n{block}" if content.strip() else block


def _render_owned_block(
    models_root: Path,
    mappings: tuple[tuple[str, tuple[Path, ...]], ...],
) -> str:
    """Render absolute paths using Comfy's multiline-path YAML contract."""

    lines = [
        _BEGIN_MARKER,
        _ROOT_PREFIX + json.dumps(str(models_root), ensure_ascii=False),
        f"{_SECTION_NAME}:",
    ]
    for kind, paths in mappings:
        lines.append(f"  {kind}: |")
        lines.extend(f"    {path.as_posix()}" for path in paths)
    lines.extend((_END_MARKER, ""))
    return "\n".join(lines)


__all__ = [
    "ComfyExternalModelPathsConfigurator",
    "ExternalModelPathsConfigurationError",
]
