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

"""Persist and load Sugar recipe documents from filesystem paths and PNG metadata."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from PIL import Image

from substitute.domain.recipes.sugar_ast import (
    LoadedRecipeDocument,
)
from substitute.shared.logging.logger import get_logger, log_error, log_debug

_LOGGER = get_logger("infrastructure.persistence.file_recipe_repository")


class FileRecipeRepository:
    """Implement recipe persistence using local filesystem and PNG metadata."""

    def has_embedded_recipe_script(self, path: Path) -> bool:
        """Return whether a PNG file contains embedded Sugar recipe metadata."""

        source_path = Path(path)
        if source_path.suffix.lower() != ".png" or not source_path.is_file():
            return False
        try:
            with Image.open(source_path) as image:
                image_text = cast(Any, image).text
                has_recipe = isinstance(image_text.get("sugar_script", None), str)
                log_debug(
                    _LOGGER,
                    "Sniffed PNG recipe metadata",
                    path=source_path,
                    image_format=image.format,
                    metadata_keys=sorted(str(key) for key in image_text),
                    has_sugar_script=has_recipe,
                )
                return has_recipe
        except Exception as error:
            log_debug(
                _LOGGER,
                "PNG recipe metadata sniff failed",
                path=source_path,
                error=error,
            )
            return False

    def load_recipe_document(self, path: Path) -> LoadedRecipeDocument:
        """Load Sugar recipe text from plain text files or PNG metadata."""

        try:
            source_path = Path(path)
            log_debug(
                _LOGGER,
                "Loading recipe document from filesystem",
                path=source_path,
                suffix=source_path.suffix.lower(),
            )
            if source_path.suffix.lower() == ".png":
                with Image.open(source_path) as image:
                    image_text = cast(Any, image).text
                    metadata_keys = sorted(str(key) for key in image_text)
                    sugar_script = image_text.get("sugar_script", None)
                    log_debug(
                        _LOGGER,
                        "Inspected PNG recipe metadata",
                        path=source_path,
                        image_format=image.format,
                        image_mode=image.mode,
                        image_size=f"{image.width}x{image.height}",
                        metadata_keys=metadata_keys,
                        has_sugar_script=sugar_script is not None,
                        sugar_script_type=type(sugar_script).__name__,
                        sugar_script_length=_text_length(sugar_script),
                        sugar_script_sha256=_text_sha256(sugar_script),
                    )
                if sugar_script is None:
                    raise ValueError("No embedded recipe found in PNG metadata.")
                log_debug(
                    _LOGGER,
                    "Loaded PNG embedded recipe document",
                    path=source_path,
                    sugar_script_length=_text_length(sugar_script),
                    sugar_script_sha256=_text_sha256(sugar_script),
                )
                return LoadedRecipeDocument(
                    sugar_script_text=sugar_script,
                    source_path=source_path,
                    source_kind="png",
                )

            sugar_script_text = source_path.read_text(encoding="utf-8")
            log_debug(
                _LOGGER,
                "Loaded text recipe document",
                path=source_path,
                sugar_script_length=len(sugar_script_text),
                sugar_script_sha256=_text_sha256(sugar_script_text),
            )
            return LoadedRecipeDocument(
                sugar_script_text=sugar_script_text,
                source_path=source_path,
                source_kind="text",
            )
        except Exception as error:
            log_error(
                _LOGGER,
                "Failed to load recipe document",
                path=path,
                error=error,
            )
            raise

    def save_recipe_document(
        self,
        path: Path,
        *,
        project_name: str,
        sugar_script_text: str,
    ) -> None:
        """Write recipe text with project header and rotate previous version backups."""

        file_path = Path(path)
        safe_project_name = project_name.strip()

        write_needed = True
        if file_path.exists():
            try:
                existing = file_path.read_text(encoding="utf-8")
                if existing == sugar_script_text:
                    write_needed = False
            except Exception:
                pass

        if not write_needed:
            return

        if file_path.exists():
            try:
                created_time = file_path.stat().st_ctime
            except Exception:
                created_time = file_path.stat().st_mtime
            timestamp = datetime.fromtimestamp(created_time).strftime("%Y%m%d_%H%M%S")
            versions_dir = file_path.parent / "versions"
            versions_dir.mkdir(exist_ok=True)
            backup_path = versions_dir / f"{file_path.stem}_{timestamp}.sugar"
            counter = 2
            while backup_path.exists():
                backup_path = (
                    versions_dir / f"{file_path.stem}_{timestamp}_{counter}.sugar"
                )
                counter += 1
            file_path.rename(backup_path)

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            f"# Project: {safe_project_name}\n\n{sugar_script_text}",
            encoding="utf-8",
        )


__all__ = [
    "FileRecipeRepository",
]


def _text_length(value: object) -> int | None:
    """Return text length for loaded recipe metadata diagnostics."""

    if isinstance(value, str):
        return len(value)
    return None


def _text_sha256(value: object) -> str:
    """Return a short deterministic hash for recipe text without logging content."""

    if not isinstance(value, str):
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
