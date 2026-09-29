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

"""Share the bounded result contract for best-effort session recovery."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

SESSION_RECOVERY_RESULT_SCHEMA_VERSION = 1


class SessionRecoveryState(str, Enum):
    """Identify how repair handled pre-existing mutable session state."""

    NO_SESSION = "no_session"
    RESTORED_PRIMARY = "restored_primary"
    RESTORED_BACKUP = "restored_backup"
    PRESERVED_NOT_RESTORED = "preserved_not_restored"


@dataclass(frozen=True, slots=True)
class SessionRecoveryResult:
    """Describe restoration separately from repair transaction success."""

    state: SessionRecoveryState
    recovery_root: Path | None = None
    detail: str = ""

    @property
    def restored(self) -> bool:
        """Return whether prior session state is usable or did not exist."""

        return self.state is not SessionRecoveryState.PRESERVED_NOT_RESTORED

    def to_json(self) -> dict[str, object]:
        """Return the stable result-file representation."""

        return {
            "schema_version": SESSION_RECOVERY_RESULT_SCHEMA_VERSION,
            "state": self.state.value,
            "recovery_root": str(self.recovery_root) if self.recovery_root else None,
            "detail": self.detail,
        }

    @classmethod
    def from_json(cls, payload: object) -> SessionRecoveryResult:
        """Load one strictly bounded recovery result."""

        if not isinstance(payload, dict):
            raise ValueError("Session recovery result must be an object.")
        if payload.get("schema_version") != SESSION_RECOVERY_RESULT_SCHEMA_VERSION:
            raise ValueError("Unsupported session recovery result schema.")
        state_value = payload.get("state")
        recovery_value = payload.get("recovery_root")
        detail = payload.get("detail")
        if (
            not isinstance(state_value, str)
            or recovery_value is not None
            and not isinstance(recovery_value, str)
            or not isinstance(detail, str)
            or len(detail) > 4096
        ):
            raise ValueError("Session recovery result fields are invalid.")
        return cls(
            state=SessionRecoveryState(state_value),
            recovery_root=Path(recovery_value) if recovery_value else None,
            detail=detail,
        )


__all__ = [
    "SESSION_RECOVERY_RESULT_SCHEMA_VERSION",
    "SessionRecoveryResult",
    "SessionRecoveryState",
]
