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

"""Own diagnostics activation and refresh lifecycle orchestration."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any, cast

from substitute.application.prompt_editor.diagnostics.display_policy import (
    PromptDiagnosticDisplayPolicy,
)
from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnosticSnapshot as ApplicationPromptDiagnosticSnapshot,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.diagnostics.spellcheck_provider import (
    PromptSpellcheckDiagnosticProvider,
)
from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)
from substitute.shared.logging.logger import get_logger, log_timing

from ..async_work import (
    PromptEditorDebouncer,
    PromptEditorMainThreadDispatcher,
    PromptEditorRequestChannel,
    QtPromptEditorDebouncer,
    QtPromptEditorMainThreadDispatcher,
)
from .diagnostics_presentation import (
    PromptDiagnosticsHost,
    PromptDiagnosticsPresentation,
    PromptDiagnosticsSurface,
)
from .diagnostics_provider_lifecycle import (
    PromptDiagnosticsProviderLifecycle,
    PromptDiagnosticsServiceFactory,
    PromptSpellcheckProviderFactory,
)
from .diagnostics_refresh_lifecycle import PromptDiagnosticsRefreshLifecycle
from .feature_profile_controller import PromptFeatureProfileController
from .wildcard_diagnostics import PromptWildcardDiagnosticsPresentation

_LOGGER = get_logger("presentation.editor.prompt_editor.features.diagnostics")


class PromptDiagnosticsFeatureController:
    """Coordinate diagnostics provider activation and bounded refresh lifecycle."""

    _DEBOUNCE_MS = 280

    def __init__(
        self,
        *,
        host: PromptDiagnosticsHost,
        surface: PromptDiagnosticsSurface,
        feature_profile: PromptFeatureProfileController,
        wildcard_feature: PromptWildcardDiagnosticsPresentation,
        document_semantics: PromptDocumentSemantics | None = None,
        spellcheck_service: PromptSpellcheckService | None = None,
        parent: object | None = None,
        bind_signals: Callable[["PromptDiagnosticsFeatureController"], None]
        | None = None,
        debouncer: PromptEditorDebouncer | None = None,
        request_channel: PromptEditorRequestChannel[ApplicationPromptDiagnosticSnapshot]
        | None = None,
        main_thread_dispatcher: PromptEditorMainThreadDispatcher | None = None,
        display_policy: PromptDiagnosticDisplayPolicy | None = None,
        diagnostics_service_factory: PromptDiagnosticsServiceFactory | None = None,
        spellcheck_provider_factory: PromptSpellcheckProviderFactory = (
            PromptSpellcheckDiagnosticProvider
        ),
        debounce_ms: int = _DEBOUNCE_MS,
    ) -> None:
        """Construct one lifecycle owner and its independent presentation owner."""

        if request_channel is None:
            raise TypeError("request_channel is required for prompt diagnostics.")
        self._providers = PromptDiagnosticsProviderLifecycle(
            feature_profile=feature_profile,
            wildcard_feature=wildcard_feature,
            document_semantics=document_semantics,
            spellcheck_service=spellcheck_service,
            service_factory=diagnostics_service_factory,
            spellcheck_provider_factory=spellcheck_provider_factory,
        )
        self._bind_signals = bind_signals
        self._activated = False
        self._activation_pending = False
        self._activation_dispatcher = (
            main_thread_dispatcher
            or QtPromptEditorMainThreadDispatcher(cast(Any, parent))
        )
        self._debouncer = debouncer or QtPromptEditorDebouncer(
            interval_ms=debounce_ms,
            parent=cast(Any, parent),
        )
        self._request_channel = request_channel
        self._presentation = PromptDiagnosticsPresentation(
            host=host,
            surface=surface,
            providers=self._providers,
            wildcard_feature=wildcard_feature,
            feature_profile_id=feature_profile.identity.feature_profile_id,
            refresh_requester=self,
            display_policy=display_policy,
        )
        self._refresh_lifecycle = PromptDiagnosticsRefreshLifecycle(
            source=host,
            providers=self._providers,
            feature_profile_id=feature_profile.identity.feature_profile_id,
            publication=self._presentation,
            debouncer=self._debouncer,
            request_channel=request_channel,
        )

    @property
    def presentation(self) -> PromptDiagnosticsPresentation:
        """Return the sole owner of diagnostics display and action state."""

        return self._presentation

    @property
    def is_active(self) -> bool:
        """Return whether diagnostics providers have been activated."""

        return self._activated

    @property
    def activation_pending(self) -> bool:
        """Return whether deferred activation is already queued."""

        return self._activation_pending

    def can_activate(self) -> bool:
        """Return whether any prompt diagnostics provider can be enabled."""

        return self._providers.can_activate()

    def schedule_activation(self) -> None:
        """Schedule optional diagnostics activation after construction settles."""

        if self._activation_pending or self._activated or not self.can_activate():
            return
        self._activation_pending = True
        self._activation_dispatcher.publish(
            self.activate,
            reason="diagnostics_activation",
        )

    @prompt_editor_work_event(PromptEditorWorkEvent.DIAGNOSTICS_ACTIVATION)
    def activate(self) -> None:
        """Create optional providers and queue an initial diagnostics refresh."""

        self._activation_pending = False
        if self._activated or not self.can_activate():
            return
        started_at = perf_counter()
        if not self._providers.activate():
            return
        if self._bind_signals is not None:
            self._bind_signals(self)
        self._activated = True
        self.handle_text_changed()
        log_timing(
            _LOGGER,
            "Initialized deferred prompt editor diagnostics services",
            started_at=started_at,
            level="debug",
        )

    def handle_text_changed(self) -> None:
        """Schedule a diagnostics refresh for the current prompt text."""

        if self._activated:
            self._refresh_lifecycle.schedule_refresh()

    def handle_document_semantics_changed(self) -> None:
        """Rebind provider translation when source interpretation changes."""

        if not self._activated:
            return
        self.clear()
        self._providers.rebuild_for_document_semantics()
        self.refresh_now()

    def refresh_now(self) -> None:
        """Refresh diagnostics for the current prompt text."""

        if self._activated:
            self._refresh_lifecycle.refresh_now()

    def refresh_visible_diagnostics(self) -> None:
        """Refresh cached diagnostics visibility after a cursor transition."""

        self._presentation.refresh_visible_diagnostics()

    def clear(self) -> None:
        """Cancel scheduled diagnostics work and clear presentation state."""

        self._refresh_lifecycle.cancel(reason="diagnostics_clear")
        self._presentation.clear()


__all__ = [
    "PromptDiagnosticsFeatureController",
]
