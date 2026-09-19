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

"""Prevent automatic retries of an exact failed application artifact."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Final, Self

from sugarsubstitute_shared.launcher_update.persistence import write_json_atomic


_SCHEMA_VERSION: Final = 1
_MAX_ENTRIES: Final = 16
_RETRYABLE_REASONS: Final = frozenset({"interrupted_activation"})


@dataclass(frozen=True, slots=True)
class QuarantinedUpdate:
    """Identify one immutable app payload that failed activation."""

    version: str
    sha256: str
    reason: str

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse one exact quarantine identity."""

        if not isinstance(payload, dict):
            raise ValueError("Update quarantine entry must be an object.")
        version = _required_text(payload.get("version"))
        digest = _required_digest(payload.get("sha256"))
        reason = _required_text(payload.get("reason"))
        return cls(version=version, sha256=digest, reason=reason)

    def to_json(self) -> dict[str, str]:
        """Return the stable entry representation."""

        return {"reason": self.reason, "sha256": self.sha256, "version": self.version}


class UpdateQuarantine:
    """Persist bounded failed target identities beneath launcher ownership."""

    def __init__(self, install_root: Path) -> None:
        """Resolve the quarantine record for one installation."""

        self._path = install_root.resolve() / "launcher" / "release-quarantine.json"

    def contains(self, *, version: str, sha256: str) -> bool:
        """Return whether the exact immutable artifact has a deterministic failure."""

        identity = (_required_text(version), _required_digest(sha256))
        return any(
            (entry.version, entry.sha256) == identity
            and entry.reason not in _RETRYABLE_REASONS
            for entry in self._load()
        )

    def add(self, *, version: str, sha256: str, reason: str) -> None:
        """Record one failed target without duplicating its identity."""

        replacement = QuarantinedUpdate(
            version=_required_text(version),
            sha256=_required_digest(sha256),
            reason=_required_text(reason),
        )
        retained = [
            entry
            for entry in self._load()
            if (entry.version, entry.sha256)
            != (replacement.version, replacement.sha256)
        ]
        self._save([replacement, *retained][:_MAX_ENTRIES])

    def remove(self, *, version: str, sha256: str) -> None:
        """Forget one target after it has been accepted successfully."""

        identity = (_required_text(version), _required_digest(sha256))
        entries = [
            entry for entry in self._load() if (entry.version, entry.sha256) != identity
        ]
        self._save(entries)

    def _load(self) -> list[QuarantinedUpdate]:
        """Load quarantine state and fail closed on corruption."""

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Update quarantine is unreadable.") from error
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Unsupported update quarantine schema.")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise ValueError("Update quarantine entries are invalid.")
        return [QuarantinedUpdate.from_json(value) for value in entries]

    def _save(self, entries: list[QuarantinedUpdate]) -> None:
        """Atomically persist the bounded quarantine record."""

        write_json_atomic(
            self._path,
            {
                "entries": [entry.to_json() for entry in entries],
                "schema_version": _SCHEMA_VERSION,
            },
        )


def _required_text(value: object) -> str:
    """Return one non-empty text value."""

    if not isinstance(value, str) or not value:
        raise ValueError("Update quarantine text must not be empty.")
    return value


def _required_digest(value: object) -> str:
    """Return one normalized SHA256 identity."""

    text = _required_text(value).lower()
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ValueError("Update quarantine SHA256 is invalid.")
    return text


__all__ = ["QuarantinedUpdate", "UpdateQuarantine"]
