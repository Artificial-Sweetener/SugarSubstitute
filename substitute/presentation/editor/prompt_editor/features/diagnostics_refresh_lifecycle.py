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

"""Own latest-wins diagnostics refresh and stale-result rejection."""

from __future__ import annotations

from typing import Protocol

from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnosticSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.shared.logging.logger import get_logger

from ..async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorDebouncer,
    PromptEditorRequestChannel,
    PromptFreshnessField,
    PromptStaleResultGuard,
    log_prompt_async_warning,
    prompt_async_outcome_log_fields,
)
from .diagnostics_provider_lifecycle import PromptDiagnosticsProviderLifecycle

_LOGGER = get_logger("presentation.editor.prompt_editor.features.diagnostics")


class PromptDiagnosticsRefreshSource(Protocol):
    """Expose source identity required for one diagnostics request."""

    def toPlainText(self) -> str:  # noqa: N802
        """Return current prompt source text."""

    def prompt_command_source_identity(self) -> PromptSourceIdentity | None:
        """Return current source identity."""


class PromptDiagnosticsRefreshPublication(Protocol):
    """Receive fresh diagnostics transitions without async implementation details."""

    def publish_empty_diagnostics(self, source_text: str) -> None:
        """Publish an empty-source result."""

    def publish_diagnostics_result(self, snapshot: PromptDiagnosticSnapshot) -> None:
        """Publish one freshness-validated diagnostics snapshot."""

    def publish_diagnostics_failure(self, error: BaseException) -> None:
        """Publish one prompt-safe diagnostics failure."""


class PromptDiagnosticsRefreshLifecycle:
    """Submit diagnostics work and reject superseded outcomes before publication."""

    def __init__(
        self,
        *,
        source: PromptDiagnosticsRefreshSource,
        providers: PromptDiagnosticsProviderLifecycle,
        feature_profile_id: object,
        publication: PromptDiagnosticsRefreshPublication,
        debouncer: PromptEditorDebouncer,
        request_channel: PromptEditorRequestChannel[PromptDiagnosticSnapshot],
    ) -> None:
        """Store refresh collaborators and bounded latest-wins state."""

        self._source = source
        self._providers = providers
        self._feature_profile_id = feature_profile_id
        self._publication = publication
        self._debouncer = debouncer
        self._request_channel = request_channel
        self._stale_guard = PromptStaleResultGuard()
        self._request_id = 0

    def schedule_refresh(self) -> None:
        """Coalesce source edits into one refresh request."""

        self._debouncer.request(self.refresh_now, reason="diagnostics_text_changed")

    def cancel(self, *, reason: str) -> None:
        """Cancel deferred and in-flight work for an invalidated diagnostics state."""

        self._debouncer.cancel(reason=reason)
        self._request_channel.cancel_pending(reason=reason)

    def refresh_now(self) -> None:
        """Submit one request from the current source snapshot."""

        self._debouncer.cancel(reason="diagnostics_refresh_now")
        source_text = self._source.toPlainText()
        if not source_text.strip():
            self._request_channel.cancel_pending(reason="diagnostics_empty_source")
            self._publication.publish_empty_diagnostics(source_text)
            return
        self._request_id += 1
        source_identity = self._source.prompt_command_source_identity()
        identity = self._identity(self._request_id, source_text, source_identity)
        service = self._providers.service
        request = PromptAsyncRequest(
            identity=identity,
            context=PromptAsyncRequestContext(
                operation="diagnostics_refresh",
                reason="text_changed",
                safe_fields=(("source_length", len(source_text)),),
            ),
            work=lambda _token: service.snapshot_for_text(source_text),
        )
        self._request_channel.submit_latest(request).add_done_callback(
            self._handle_outcome,
            reason="diagnostics_refresh_completed",
        )

    def _handle_outcome(
        self, outcome: PromptAsyncTaskOutcome[PromptDiagnosticSnapshot]
    ) -> None:
        """Publish only a non-cancelled, non-failed, current-source outcome."""

        if outcome.cancelled:
            return
        if outcome.error is not None:
            log_prompt_async_warning(
                _LOGGER,
                "prompt_diagnostics.refresh.failed",
                error=outcome.error,
                **prompt_async_outcome_log_fields(outcome),
            )
            self._publication.publish_diagnostics_failure(outcome.error)
            return
        result = outcome.result
        if result is None:
            return
        source_text = self._source.toPlainText()
        current_identity = self._identity(
            self._request_id,
            source_text,
            self._source.prompt_command_source_identity(),
        )
        required_fields: list[PromptFreshnessField] = [
            "request_id",
            "feature_profile_id",
        ]
        if current_identity.source_identity is not None:
            required_fields.append("source_identity")
        if (
            not self._stale_guard.validate(
                result_identity=outcome.identity,
                current_identity=current_identity,
                required_fields=required_fields,
            ).is_fresh
            or result.source_text != source_text
        ):
            return
        self._publication.publish_diagnostics_result(result)

    def _identity(
        self,
        request_id: int,
        source_text: str,
        source_identity: PromptSourceIdentity | None,
    ) -> PromptAsyncResultIdentity:
        """Build a prompt-safe latest-wins identity."""

        return PromptAsyncResultIdentity(
            request_id=request_id,
            source_identity=(
                PromptSourceIdentity(source_identity.source_revision, len(source_text))
                if source_identity is not None
                else None
            ),
            feature_profile_id=(
                self._feature_profile_id,
                self._providers.conditioning_context_identity,
            ),
        )


__all__ = [
    "PromptDiagnosticsRefreshLifecycle",
    "PromptDiagnosticsRefreshPublication",
    "PromptDiagnosticsRefreshSource",
]
