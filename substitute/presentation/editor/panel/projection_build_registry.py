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

"""Track pure cube-section build lifecycle state for editor projection."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Literal

from .projection_preparation import CubeDefinitionIdentity

BuildState = Literal["building", "complete", "stale", "failed", "cancelled"]


@dataclass(slots=True)
class CubeSectionBuildRecord:
    """Track the lifecycle of one projected cube section."""

    alias: str
    token: object
    widget: object
    session: object | None
    state: BuildState
    snapshot_identity: object | None
    definition_identity: CubeDefinitionIdentity | None
    started_at: float
    completed_at: float | None = None
    stale_reason: str | None = None
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class CubeSectionBuildReuseDecision:
    """Report whether an existing cube-section widget remains reusable."""

    can_reuse: bool
    record_present: bool
    record_state: BuildState | None
    active_token: object | None
    definition_identity: CubeDefinitionIdentity | None


@dataclass(frozen=True, slots=True)
class CubeSectionBuildStaleResult:
    """Report the lifecycle impact of marking one cube-section build stale."""

    alias: str
    record_present: bool
    was_building: bool
    active_token: object | None
    state: BuildState | None


class CubeSectionBuildRegistry:
    """Own alias-scoped cube section build lifecycle state."""

    def __init__(self) -> None:
        """Initialize an empty cube-section build registry."""

        self._records: dict[str, CubeSectionBuildRecord] = {}

    def start(
        self,
        *,
        alias: str,
        widget: object,
        session: object | None,
        snapshot_identity: object | None,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> object:
        """Record a building cube section and return its ownership token."""

        token = object()
        self._records[alias] = CubeSectionBuildRecord(
            alias=alias,
            token=token,
            widget=widget,
            session=session,
            state="building",
            snapshot_identity=snapshot_identity,
            definition_identity=definition_identity,
            started_at=perf_counter(),
        )
        return token

    def adopt_complete(
        self,
        *,
        alias: str,
        widget: object,
        snapshot_identity: object | None,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> None:
        """Adopt an existing widget as complete when no active record exists."""

        self._records[alias] = CubeSectionBuildRecord(
            alias=alias,
            token=object(),
            widget=widget,
            session=None,
            state="complete",
            snapshot_identity=snapshot_identity,
            definition_identity=definition_identity,
            started_at=perf_counter(),
            completed_at=perf_counter(),
        )

    def record_for(self, alias: str) -> CubeSectionBuildRecord | None:
        """Return the current build record for an alias."""

        return self._records.get(alias)

    def is_current(self, alias: str, token: object) -> bool:
        """Return whether one token still owns an active build."""

        record = self._records.get(alias)
        return (
            record is not None and record.token is token and record.state == "building"
        )

    def mark_complete(self, alias: str, token: object) -> bool:
        """Mark one active build complete when the token still owns it."""

        record = self._records.get(alias)
        if record is None or record.token is not token or record.state != "building":
            return False
        record.state = "complete"
        record.completed_at = perf_counter()
        record.stale_reason = None
        record.failure = None
        return True

    def mark_stale(self, alias: str, reason: str) -> CubeSectionBuildStaleResult:
        """Mark one existing build record stale and report active-build impact."""

        record = self._records.get(alias)
        if record is None:
            return CubeSectionBuildStaleResult(
                alias=alias,
                record_present=False,
                was_building=False,
                active_token=None,
                state=None,
            )
        was_building = record.state == "building"
        active_token = record.token if was_building else None
        record.state = "stale"
        record.stale_reason = reason
        return CubeSectionBuildStaleResult(
            alias=alias,
            record_present=True,
            was_building=was_building,
            active_token=active_token,
            state=record.state,
        )

    def mark_failed(self, alias: str, token: object, error: object) -> bool:
        """Mark one active build failed when the token still owns it."""

        record = self._records.get(alias)
        if record is None or record.token is not token or record.state != "building":
            return False
        record.state = "failed"
        record.failure = repr(error)
        return True

    def cancel(self, alias: str, token: object, reason: str) -> bool:
        """Cancel one active or stale build when the token still owns it."""

        record = self._records.get(alias)
        if record is None or record.token is not token:
            return False
        if record.state not in {"building", "stale"}:
            return False
        record.state = "cancelled"
        record.stale_reason = reason
        return True

    def forget(self, alias: str) -> CubeSectionBuildRecord | None:
        """Remove one build record."""

        return self._records.pop(alias, None)

    def clear(self) -> None:
        """Forget every tracked cube-section build record."""

        self._records.clear()

    def reuse_decision(
        self,
        alias: str,
        widget: object,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> CubeSectionBuildReuseDecision:
        """Decide whether one widget is complete and safe to reuse."""

        record = self._records.get(alias)
        if record is None:
            self.adopt_complete(
                alias=alias,
                widget=widget,
                snapshot_identity=None,
                definition_identity=definition_identity,
            )
            record = self._records[alias]
        can_reuse = (
            record.widget is widget
            and record.state == "complete"
            and record.definition_identity == definition_identity
        )
        active_token = record.token if record.state == "building" else None
        return CubeSectionBuildReuseDecision(
            can_reuse=can_reuse,
            record_present=True,
            record_state=record.state,
            active_token=active_token,
            definition_identity=record.definition_identity,
        )

    def can_reuse(
        self,
        alias: str,
        widget: object,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> bool:
        """Return whether one widget is complete and not stale or active."""

        return self.reuse_decision(alias, widget, definition_identity).can_reuse
