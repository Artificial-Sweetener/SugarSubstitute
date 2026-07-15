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

"""Define pure shared canvas session identity and stale-update authorization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class CanvasKind(StrEnum):
    """Identify the shared canvas surface a session controls."""

    INPUT = "input"
    OUTPUT = "output"


class CanvasSessionRejectionReason(StrEnum):
    """Describe why a session token cannot authorize visible mutation."""

    MISSING_SESSION = "missing_session"
    WORKFLOW_MISMATCH = "workflow_mismatch"
    CANVAS_KIND_MISMATCH = "canvas_kind_mismatch"
    STALE_REVISION = "stale_revision"
    ROUTE_MISMATCH = "route_mismatch"


@dataclass(frozen=True, slots=True)
class CanvasWorkflowIdentity:
    """Carry the workflow id that owns one active canvas session."""

    value: str


@dataclass(frozen=True, slots=True)
class CanvasSessionRevision:
    """Identify one active session binding generation for a canvas kind."""

    value: int

    def __post_init__(self) -> None:
        """Reject negative session revisions."""

        if self.value < 0:
            raise ValueError("Canvas session revision cannot be negative.")

    def next(self) -> CanvasSessionRevision:
        """Return the next monotonic revision value."""

        return CanvasSessionRevision(self.value + 1)


@dataclass(frozen=True, slots=True)
class CanvasRouteIdentity:
    """Describe the active canvas route without deciding route policy."""

    route_kind: str
    route_key: str
    primary_image_id: UUID | None = None

    @classmethod
    def empty(cls) -> CanvasRouteIdentity:
        """Return the canonical empty route identity."""

        return cls(route_kind="empty", route_key="")


@dataclass(frozen=True, slots=True)
class CanvasGenerationIdentity:
    """Carry Output generation/run identity when a route has one."""

    generation_run_id: str
    prompt_id: str
    client_id: str

    def __post_init__(self) -> None:
        """Reject incomplete Output generation identity packets."""

        if not self.generation_run_id:
            raise ValueError("Output canvas generation identity requires a run ID.")
        if not self.prompt_id:
            raise ValueError("Output canvas generation identity requires a prompt ID.")
        if not self.client_id:
            raise ValueError("Output canvas generation identity requires a client ID.")


@dataclass(frozen=True, slots=True)
class CanvasSessionToken:
    """Capture the session identity a later display mutation must prove current."""

    workflow_id: CanvasWorkflowIdentity
    canvas_kind: CanvasKind
    revision: CanvasSessionRevision
    active_route: CanvasRouteIdentity


@dataclass(frozen=True, slots=True)
class CanvasSession:
    """Bind one workflow, canvas kind, revision, and active route."""

    workflow_id: CanvasWorkflowIdentity
    canvas_kind: CanvasKind
    revision: CanvasSessionRevision
    active_route: CanvasRouteIdentity

    def token(self) -> CanvasSessionToken:
        """Return a stale-check token for later display mutation attempts."""

        return CanvasSessionToken(
            workflow_id=self.workflow_id,
            canvas_kind=self.canvas_kind,
            revision=self.revision,
            active_route=self.active_route,
        )


@dataclass(frozen=True, slots=True)
class InputCanvasSession:
    """Bind the active Input canvas route without generation identity."""

    session: CanvasSession

    def __post_init__(self) -> None:
        """Ensure this session is explicitly an Input canvas session."""

        if self.session.canvas_kind is not CanvasKind.INPUT:
            raise ValueError("Input canvas sessions must use CanvasKind.INPUT.")

    @property
    def workflow_id(self) -> CanvasWorkflowIdentity:
        """Return the workflow identity bound to this session."""

        return self.session.workflow_id

    @property
    def canvas_kind(self) -> CanvasKind:
        """Return the canvas kind bound to this session."""

        return self.session.canvas_kind

    @property
    def revision(self) -> CanvasSessionRevision:
        """Return this session's stale-check revision."""

        return self.session.revision

    @property
    def active_route(self) -> CanvasRouteIdentity:
        """Return the active route identity for this session."""

        return self.session.active_route

    def token(self) -> CanvasSessionToken:
        """Return a stale-check token for later display mutation attempts."""

        return self.session.token()


@dataclass(frozen=True, slots=True)
class OutputCanvasSession:
    """Bind the active Output canvas route and optional generation identity."""

    session: CanvasSession
    generation_identity: CanvasGenerationIdentity | None = None

    def __post_init__(self) -> None:
        """Ensure this session is explicitly an Output canvas session."""

        if self.session.canvas_kind is not CanvasKind.OUTPUT:
            raise ValueError("Output canvas sessions must use CanvasKind.OUTPUT.")

    @property
    def workflow_id(self) -> CanvasWorkflowIdentity:
        """Return the workflow identity bound to this session."""

        return self.session.workflow_id

    @property
    def canvas_kind(self) -> CanvasKind:
        """Return the canvas kind bound to this session."""

        return self.session.canvas_kind

    @property
    def revision(self) -> CanvasSessionRevision:
        """Return this session's stale-check revision."""

        return self.session.revision

    @property
    def active_route(self) -> CanvasRouteIdentity:
        """Return the active route identity for this session."""

        return self.session.active_route

    def token(self) -> CanvasSessionToken:
        """Return a stale-check token for later display mutation attempts."""

        return self.session.token()


@dataclass(frozen=True, slots=True)
class CanvasMutationAuthorization:
    """Report whether a session token may authorize visible mutation."""

    accepted: bool
    rejection_reason: CanvasSessionRejectionReason | None = None


CanvasBoundSession = InputCanvasSession | OutputCanvasSession


class CanvasSessionBoundary:
    """Own active canvas session identity and stale-token rejection."""

    def __init__(self) -> None:
        """Create an empty shared session boundary."""

        self._sessions: dict[CanvasKind, CanvasBoundSession] = {}
        self._revisions: dict[CanvasKind, CanvasSessionRevision] = {
            CanvasKind.INPUT: CanvasSessionRevision(0),
            CanvasKind.OUTPUT: CanvasSessionRevision(0),
        }

    def bind_input_session(
        self,
        *,
        workflow_id: str,
        active_route: CanvasRouteIdentity,
    ) -> InputCanvasSession:
        """Bind the active Input session and return its new identity."""

        revision = self._next_revision(CanvasKind.INPUT)
        shared_session = CanvasSession(
            workflow_id=CanvasWorkflowIdentity(workflow_id),
            canvas_kind=CanvasKind.INPUT,
            revision=revision,
            active_route=active_route,
        )
        session = InputCanvasSession(session=shared_session)
        self._sessions[CanvasKind.INPUT] = session
        return session

    def bind_output_session(
        self,
        *,
        workflow_id: str,
        active_route: CanvasRouteIdentity,
        generation_identity: CanvasGenerationIdentity | None = None,
    ) -> OutputCanvasSession:
        """Bind the active Output session and return its new identity."""

        revision = self._next_revision(CanvasKind.OUTPUT)
        shared_session = CanvasSession(
            workflow_id=CanvasWorkflowIdentity(workflow_id),
            canvas_kind=CanvasKind.OUTPUT,
            revision=revision,
            active_route=active_route,
        )
        session = OutputCanvasSession(
            session=shared_session,
            generation_identity=generation_identity,
        )
        self._sessions[CanvasKind.OUTPUT] = session
        return session

    def current_session(self, canvas_kind: CanvasKind) -> CanvasBoundSession | None:
        """Return the current session for one canvas kind, when bound."""

        return self._sessions.get(canvas_kind)

    def adopt_session(self, session: CanvasBoundSession) -> bool:
        """Adopt a current-or-newer externally minted canvas session."""

        current = self._sessions.get(session.canvas_kind)
        current_revision = self._revisions[session.canvas_kind]
        if current is not None and current == session:
            return True
        if session.revision.value <= current_revision.value:
            return False
        self._sessions[session.canvas_kind] = session
        self._revisions[session.canvas_kind] = session.revision
        return True

    def authorize_display_mutation(
        self,
        token: CanvasSessionToken,
        *,
        canvas_kind: CanvasKind | None = None,
        active_route: CanvasRouteIdentity | None = None,
    ) -> CanvasMutationAuthorization:
        """Return whether a token still matches the active canvas session."""

        if canvas_kind is not None and token.canvas_kind is not canvas_kind:
            return CanvasMutationAuthorization(
                accepted=False,
                rejection_reason=CanvasSessionRejectionReason.CANVAS_KIND_MISMATCH,
            )
        current = self._sessions.get(token.canvas_kind)
        if current is None:
            return CanvasMutationAuthorization(
                accepted=False,
                rejection_reason=CanvasSessionRejectionReason.MISSING_SESSION,
            )
        if current.canvas_kind is not token.canvas_kind:
            return CanvasMutationAuthorization(
                accepted=False,
                rejection_reason=CanvasSessionRejectionReason.CANVAS_KIND_MISMATCH,
            )
        if current.workflow_id != token.workflow_id:
            return CanvasMutationAuthorization(
                accepted=False,
                rejection_reason=CanvasSessionRejectionReason.WORKFLOW_MISMATCH,
            )
        if current.revision != token.revision:
            return CanvasMutationAuthorization(
                accepted=False,
                rejection_reason=CanvasSessionRejectionReason.STALE_REVISION,
            )
        if current.active_route != token.active_route:
            return CanvasMutationAuthorization(
                accepted=False,
                rejection_reason=CanvasSessionRejectionReason.ROUTE_MISMATCH,
            )
        if active_route is not None and current.active_route != active_route:
            return CanvasMutationAuthorization(
                accepted=False,
                rejection_reason=CanvasSessionRejectionReason.ROUTE_MISMATCH,
            )
        return CanvasMutationAuthorization(accepted=True)

    def _next_revision(self, canvas_kind: CanvasKind) -> CanvasSessionRevision:
        """Advance and return the revision for one canvas kind."""

        revision = self._revisions[canvas_kind].next()
        self._revisions[canvas_kind] = revision
        return revision


__all__ = [
    "CanvasGenerationIdentity",
    "CanvasKind",
    "CanvasMutationAuthorization",
    "CanvasRouteIdentity",
    "CanvasBoundSession",
    "CanvasSession",
    "CanvasSessionBoundary",
    "CanvasSessionRejectionReason",
    "CanvasSessionRevision",
    "CanvasSessionToken",
    "CanvasWorkflowIdentity",
    "InputCanvasSession",
    "OutputCanvasSession",
]
