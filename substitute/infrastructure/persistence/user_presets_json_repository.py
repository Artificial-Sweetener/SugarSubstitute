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

"""Persist user presets in a versioned JSON file under user storage."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast

from substitute.domain.common import JsonObject
from substitute.domain.user_presets import (
    UserPreset,
    decode_user_presets_document,
    encode_user_presets_document,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.user_presets_json_repository")


class JsonUserPresetRepository:
    """Read and write user-created presets from ``user/presets.json``."""

    def __init__(self, user_root: Path) -> None:
        """Store the resolved user preset file path."""

        self._user_root = user_root.resolve()
        self._preset_path = self._user_root / "presets.json"

    @property
    def preset_path(self) -> Path:
        """Return the concrete user preset JSON path."""

        return self._preset_path

    def load_presets(self) -> tuple[UserPreset, ...]:
        """Return valid user presets from storage, or none on miss or damage."""

        if not self._preset_path.exists():
            return ()
        try:
            raw_payload = json.loads(self._preset_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to read user presets JSON",
                path=self._preset_path,
                error=repr(error),
            )
            return ()
        if not isinstance(raw_payload, dict):
            log_warning(
                _LOGGER,
                "User presets JSON root is not an object",
                path=self._preset_path,
            )
            return ()
        return decode_user_presets_document(cast(JsonObject, raw_payload))

    def save_presets(self, presets: tuple[UserPreset, ...]) -> None:
        """Persist user presets with a same-directory atomic replacement."""

        payload = encode_user_presets_document(presets)
        self._preset_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self._preset_path.parent,
            delete=False,
            suffix=".tmp",
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary_path.replace(self._preset_path)


__all__ = ["JsonUserPresetRepository"]
