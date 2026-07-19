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

"""Persist named prompt autocomplete tag lists beneath the user folder."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from substitute.application.prompt_autocomplete_lists import (
    PromptAutocompleteList,
    PromptAutocompleteListKind,
    PromptAutocompleteListRepository,
)
from substitute.shared.logging.logger import get_logger, log_warning
from substitute.shared.util.path_safety import ensure_within_root

_LOGGER = get_logger("infrastructure.persistence.prompt_autocomplete_lists")
_STATE_FILE_NAME = "lists.json"
_STATE_VERSION = 1


class FilePromptAutocompleteListRepository(PromptAutocompleteListRepository):
    """Store list content as TXT files and enablement as small JSON state."""

    def __init__(self, user_root: Path) -> None:
        """Configure the Substitute user autocomplete directory."""

        self._root = Path(user_root) / "autocomplete"

    def list_lists(self) -> tuple[PromptAutocompleteList, ...]:
        """Return custom and censored TXT lists in stable display order."""

        disabled_ids = self._disabled_ids()
        lists: list[PromptAutocompleteList] = []
        for kind in PromptAutocompleteListKind:
            directory = self._kind_root(kind)
            directory.mkdir(parents=True, exist_ok=True)
            for path in sorted(directory.rglob("*.txt")):
                if not path.is_file():
                    continue
                safe_path = ensure_within_root(
                    path,
                    root_path=directory,
                    subject="prompt autocomplete list",
                )
                relative = safe_path.relative_to(directory).as_posix()
                list_id = f"{kind.value}/{relative}"
                try:
                    text = safe_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as error:
                    log_warning(
                        _LOGGER,
                        "Skipping unreadable prompt autocomplete list",
                        list_id=list_id,
                        error=repr(error),
                    )
                    continue
                lists.append(
                    PromptAutocompleteList(
                        id=list_id,
                        name=PurePosixPath(relative).with_suffix("").as_posix(),
                        kind=kind,
                        enabled=list_id not in disabled_ids,
                        text=text,
                    )
                )
        return tuple(lists)

    def create_list(
        self,
        *,
        name: str,
        kind: PromptAutocompleteListKind,
        text: str,
    ) -> PromptAutocompleteList:
        """Create one enabled TXT list inside its kind namespace."""

        list_id = self._list_id(kind, name)
        path = self._path_for_id(list_id)
        if path.exists():
            raise FileExistsError(f"Autocomplete list already exists: {name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        disabled = self._disabled_ids()
        disabled.discard(list_id)
        self._save_disabled_ids(disabled)
        return self._required_list(list_id)

    def read_text(self, list_id: str) -> str:
        """Read one validated list path."""

        return self._path_for_id(list_id).read_text(encoding="utf-8")

    def write_text(self, list_id: str, text: str) -> PromptAutocompleteList:
        """Replace one validated list's content."""

        self._path_for_id(list_id).write_text(text, encoding="utf-8")
        return self._required_list(list_id)

    def rename_list(self, list_id: str, name: str) -> PromptAutocompleteList:
        """Rename one list without moving it between list kinds."""

        kind, _relative = self._parts_for_id(list_id)
        new_id = self._list_id(kind, name)
        old_path = self._path_for_id(list_id)
        new_path = self._path_for_id(new_id)
        if new_path.exists():
            raise FileExistsError(f"Autocomplete list already exists: {name}")
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
        disabled = self._disabled_ids()
        if list_id in disabled:
            disabled.remove(list_id)
            disabled.add(new_id)
            self._save_disabled_ids(disabled)
        return self._required_list(new_id)

    def delete_list(self, list_id: str) -> None:
        """Delete one list and remove stale enablement state."""

        path = self._path_for_id(list_id)
        if path.exists():
            path.unlink()
        disabled = self._disabled_ids()
        if list_id in disabled:
            disabled.remove(list_id)
            self._save_disabled_ids(disabled)

    def set_enabled(self, list_id: str, enabled: bool) -> PromptAutocompleteList:
        """Persist whether one existing list participates in autocomplete."""

        self._required_list(list_id)
        disabled = self._disabled_ids()
        if enabled:
            disabled.discard(list_id)
        else:
            disabled.add(list_id)
        self._save_disabled_ids(disabled)
        return self._required_list(list_id)

    def _required_list(self, list_id: str) -> PromptAutocompleteList:
        """Return one current list or fail when it does not exist."""

        for autocomplete_list in self.list_lists():
            if autocomplete_list.id == list_id:
                return autocomplete_list
        raise FileNotFoundError(f"Autocomplete list not found: {list_id}")

    def _list_id(self, kind: PromptAutocompleteListKind, name: str) -> str:
        """Return a normalized kind-qualified TXT identifier."""

        normalized = name.strip().replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.suffix.casefold() == ".txt":
            path = path.with_suffix("")
        if not normalized or path.is_absolute():
            raise ValueError("Autocomplete list name must be relative.")
        if any(part in {"", ".", ".."} or ":" in part for part in path.parts):
            raise ValueError("Autocomplete list name contains an unsafe path part.")
        return f"{kind.value}/{path.as_posix()}.txt"

    def _path_for_id(self, list_id: str) -> Path:
        """Resolve a validated kind-qualified identifier beneath its root."""

        kind, relative = self._parts_for_id(list_id)
        root = self._kind_root(kind)
        return ensure_within_root(
            root / Path(*relative.parts),
            root_path=root,
            subject="prompt autocomplete list",
        )

    def _parts_for_id(
        self, list_id: str
    ) -> tuple[PromptAutocompleteListKind, PurePosixPath]:
        """Parse and validate one persisted list identifier."""

        path = PurePosixPath(list_id.strip().replace("\\", "/"))
        if path.is_absolute() or len(path.parts) < 2:
            raise ValueError("Autocomplete list id must include its kind.")
        try:
            kind = PromptAutocompleteListKind(path.parts[0])
        except ValueError as error:
            raise ValueError("Unknown autocomplete list kind.") from error
        relative = PurePosixPath(*path.parts[1:])
        if relative.suffix.casefold() != ".txt" or any(
            part in {"", ".", ".."} or ":" in part for part in relative.parts
        ):
            raise ValueError("Autocomplete list id must be a safe TXT path.")
        return kind, relative

    def _kind_root(self, kind: PromptAutocompleteListKind) -> Path:
        """Return the storage root for one list kind."""

        return self._root / kind.value

    def _disabled_ids(self) -> set[str]:
        """Load disabled list ids, failing open for malformed preference state."""

        path = self._root / _STATE_FILE_NAME
        if not path.exists():
            return set()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load autocomplete list state; enabling all lists",
                error=repr(error),
            )
            return set()
        if not isinstance(payload, dict):
            return set()
        disabled = payload.get("disabled")
        if not isinstance(disabled, list):
            return set()
        return {value for value in disabled if isinstance(value, str)}

    def _save_disabled_ids(self, disabled_ids: set[str]) -> None:
        """Persist stable enabled-list state separately from portable TXT content."""

        self._root.mkdir(parents=True, exist_ok=True)
        payload = {"version": _STATE_VERSION, "disabled": sorted(disabled_ids)}
        (self._root / _STATE_FILE_NAME).write_text(
            f"{json.dumps(payload, indent=2)}\n", encoding="utf-8"
        )


__all__ = ["FilePromptAutocompleteListRepository"]
