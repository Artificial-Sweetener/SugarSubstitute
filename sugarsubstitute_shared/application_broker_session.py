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

"""Define the owner-session operations used by launcher orchestration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation


DELEGATED_LAUNCHER_ENV = "SUGAR_SUBSTITUTE_DELEGATED_LAUNCHER"


class ApplicationBrokerSession(Protocol):
    """Keep lifecycle coordination independent of local or delegated broker access."""

    def child_environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """Authorize a child through the retained installation owner."""

    def consume_restart_request(self) -> bool:
        """Consume exactly one pending restart at its authoritative owner."""

    def bind_startup_presenter(
        self, presenter: Callable[[ApplicationInvocation], str | None] | None
    ) -> None:
        """Expose an available startup surface until the application registers."""

    def close(self) -> None:
        """Release only the resources owned by this session."""
