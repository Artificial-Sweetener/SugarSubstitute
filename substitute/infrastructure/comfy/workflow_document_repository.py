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

"""Read direct Comfy workflow documents from JSON files and PNG metadata."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from PIL import Image

from substitute.domain.common import JsonObject
from substitute.shared.logging.logger import get_logger, log_debug

_MAX_WORKFLOW_BYTES = 64 * 1024 * 1024
_LOGGER = get_logger("infrastructure.comfy.workflow_document_repository")


class ComfyWorkflowDocumentRepository:
    """Decode bounded Comfy workflow objects from supported document containers."""

    def can_load(self, path: Path) -> bool:
        """Return whether a path identifies an available direct Comfy workflow."""

        source_path = Path(path)
        suffix = source_path.suffix.casefold()
        if suffix == ".json":
            return True
        if suffix != ".png" or not source_path.is_file():
            return False
        try:
            metadata = _read_png_text_metadata(source_path)
        except (OSError, SyntaxError, ValueError) as error:
            log_debug(
                _LOGGER,
                "Failed to inspect PNG workflow metadata",
                source_path=source_path,
                error=error,
            )
            return False
        has_sugar_script = isinstance(metadata.get("sugar_script"), str)
        has_comfy_workflow = isinstance(metadata.get("workflow"), str)
        log_debug(
            _LOGGER,
            "Inspected PNG workflow metadata",
            source_path=source_path,
            metadata_keys=sorted(metadata),
            has_sugar_script=has_sugar_script,
            has_comfy_workflow=has_comfy_workflow,
            direct_workflow_available=has_comfy_workflow and not has_sugar_script,
        )
        return has_comfy_workflow and not has_sugar_script

    def load(self, path: Path) -> JsonObject:
        """Return a validated top-level Comfy workflow object from a document."""

        source_path = Path(path).resolve()
        suffix = source_path.suffix.casefold()
        if suffix not in {".json", ".png"}:
            raise ValueError("Comfy workflow files must use .json or .png.")
        if not source_path.is_file():
            raise FileNotFoundError(
                f"Comfy workflow file does not exist: {source_path}"
            )
        if suffix == ".json":
            return _decode_workflow_json(_read_json_document(source_path))
        return _decode_workflow_json(_read_png_workflow(source_path))


def _read_json_document(source_path: Path) -> str:
    """Read one bounded UTF-8 JSON workflow document."""

    if source_path.stat().st_size > _MAX_WORKFLOW_BYTES:
        raise ValueError("Comfy workflow JSON exceeds the 64 MiB safety limit.")
    return source_path.read_text(encoding="utf-8-sig")


def _read_png_workflow(source_path: Path) -> str:
    """Return workflow JSON from PNG text metadata after enforcing precedence."""

    metadata = _read_png_text_metadata(source_path)
    if isinstance(metadata.get("sugar_script"), str):
        raise ValueError(
            "PNG contains SugarScript metadata and must use the SugarScript loader."
        )
    workflow = metadata.get("workflow")
    if not isinstance(workflow, str):
        raise ValueError("PNG does not contain an embedded Comfy workflow.")
    if len(workflow.encode("utf-8")) > _MAX_WORKFLOW_BYTES:
        raise ValueError(
            "Embedded Comfy workflow JSON exceeds the 64 MiB safety limit."
        )
    return workflow


def _read_png_text_metadata(source_path: Path) -> dict[str, object]:
    """Return detached PNG text metadata without decoding image pixels."""

    with Image.open(source_path) as image:
        raw_metadata = cast(Any, image).text
        if not isinstance(raw_metadata, Mapping):
            return {}
        return {str(key): value for key, value in raw_metadata.items()}


def _decode_workflow_json(serialized_workflow: str) -> JsonObject:
    """Decode and validate one serialized top-level workflow object."""

    try:
        payload = json.loads(serialized_workflow)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Comfy workflow JSON is invalid at line {error.lineno}, "
            f"column {error.colno}."
        ) from error
    if not isinstance(payload, dict):
        raise ValueError("Comfy workflow JSON must contain a top-level object.")
    return payload


__all__ = ["ComfyWorkflowDocumentRepository"]
