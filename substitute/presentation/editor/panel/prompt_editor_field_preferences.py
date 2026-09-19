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

"""Own persisted per-field prompt editor presentation preferences."""

from __future__ import annotations

from collections.abc import Callable

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.prompt_editor_field_preferences")
_MANUAL_HEIGHTS_KEY = "prompt_editor_manual_heights"
_RICH_RENDERING_KEY = "prompt_editor_rich_rendering"


class PromptEditorFieldPreferences:
    """Read and mutate prompt presentation metadata on one workflow state."""

    def __init__(self, mark_dirty: Callable[[object], None]) -> None:
        """Store the workflow dirty-state collaborator."""

        self._mark_dirty = mark_dirty

    def manual_height(self, cube_state: object, field_identity: str) -> int | None:
        """Return one valid stored prompt editor height."""

        heights = self._mapping(cube_state, _MANUAL_HEIGHTS_KEY)
        value = heights.get(field_identity) if heights is not None else None
        return value if type(value) is int and value > 0 else None

    def rich_rendering_enabled(
        self,
        cube_state: object,
        field_identity: str,
    ) -> bool | None:
        """Return one valid stored rich-rendering preference."""

        preferences = self._mapping(cube_state, _RICH_RENDERING_KEY)
        value = preferences.get(field_identity) if preferences is not None else None
        if value is None:
            return None
        if type(value) is bool:
            return value
        log_warning(
            _LOGGER,
            "Ignored invalid prompt editor rich-rendering preference",
            field_identity=field_identity,
            enabled=repr(value),
        )
        return None

    def store_manual_height(
        self,
        cube_state: object,
        field_identity: str,
        height: object,
    ) -> bool:
        """Persist or clear one prompt editor manual height."""

        if height is None:
            return self._clear(cube_state, _MANUAL_HEIGHTS_KEY, field_identity)
        if type(height) is not int or height <= 0:
            log_warning(
                _LOGGER,
                "Ignored invalid prompt editor manual height",
                field_identity=field_identity,
                height=repr(height),
            )
            return False
        return self._store(cube_state, _MANUAL_HEIGHTS_KEY, field_identity, height)

    def store_rich_rendering_enabled(
        self,
        cube_state: object,
        field_identity: str,
        enabled: object,
    ) -> bool:
        """Persist non-default rich rendering or clear its stored override."""

        if type(enabled) is not bool:
            log_warning(
                _LOGGER,
                "Ignored invalid prompt editor rich-rendering preference change",
                field_identity=field_identity,
                enabled=repr(enabled),
            )
            return False
        if enabled:
            return self._clear(cube_state, _RICH_RENDERING_KEY, field_identity)
        return self._store(cube_state, _RICH_RENDERING_KEY, field_identity, False)

    @staticmethod
    def _mapping(cube_state: object, key: str) -> dict[str, object] | None:
        """Return one stored preference mapping when valid."""

        ui_payload = getattr(cube_state, "ui", None)
        if not isinstance(ui_payload, dict):
            return None
        values = ui_payload.get(key)
        return values if isinstance(values, dict) else None

    @staticmethod
    def _mutable_ui(cube_state: object) -> dict[str, object]:
        """Return mutable Cube UI metadata, creating it when absent."""

        ui_payload = getattr(cube_state, "ui", None)
        if not isinstance(ui_payload, dict):
            ui_payload = {}
            setattr(cube_state, "ui", ui_payload)
        return ui_payload

    def _store(
        self,
        cube_state: object,
        key: str,
        field_identity: str,
        value: object,
    ) -> bool:
        """Store one changed preference and mark its workflow dirty."""

        ui_payload = self._mutable_ui(cube_state)
        values = ui_payload.get(key)
        if not isinstance(values, dict):
            values = {}
            ui_payload[key] = values
        if values.get(field_identity) == value:
            return False
        values[field_identity] = value
        self._mark_dirty(cube_state)
        return True

    def _clear(self, cube_state: object, key: str, field_identity: str) -> bool:
        """Remove one stored preference when present."""

        ui_payload = getattr(cube_state, "ui", None)
        if not isinstance(ui_payload, dict):
            return False
        values = ui_payload.get(key)
        if not isinstance(values, dict) or field_identity not in values:
            return False
        del values[field_identity]
        if not values:
            ui_payload.pop(key, None)
        self._mark_dirty(cube_state)
        return True


__all__ = ["PromptEditorFieldPreferences"]
