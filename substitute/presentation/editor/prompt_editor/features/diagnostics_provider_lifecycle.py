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

"""Own diagnostics provider activation and document-semantics construction."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.application.prompt_editor.diagnostics.coordinator import (
    PromptDiagnosticProvider,
    PromptDiagnosticsService,
)
from substitute.application.prompt_editor.diagnostics.duplicate_segments import (
    PromptDuplicateSegmentDiagnosticProvider,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.diagnostics.spellcheck_provider import (
    PromptSpellcheckDiagnosticProvider,
)
from substitute.application.prompt_editor.conditioning import (
    PromptConditioningContext,
    unbound_prompt_conditioning_context,
)
from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptDocumentSemantics,
)
from substitute.application.prompt_editor.diagnostics.unsupported_scenes import (
    PromptUnsupportedSceneMarkerDiagnosticProvider,
)
from substitute.application.prompt_editor.diagnostics.structured_values import (
    PromptStructuredValueDiagnosticProvider,
)

from .feature_profile_controller import PromptFeatureProfileController


class PromptWildcardDiagnosticProviderSource(Protocol):
    """Provide the wildcard diagnostic topology required by diagnostics lifecycle."""

    def diagnostic_provider_ready(self) -> bool:
        """Return whether wildcard diagnostics are enabled."""

    def diagnostic_providers(self) -> tuple[PromptDiagnosticProvider, ...]:
        """Return the prepared wildcard diagnostic providers."""


type PromptDiagnosticsServiceFactory = Callable[
    [tuple[PromptDiagnosticProvider, ...]],
    PromptDiagnosticsService,
]
type PromptSpellcheckProviderFactory = Callable[
    [PromptSpellcheckService],
    PromptSpellcheckDiagnosticProvider,
]


class PromptDiagnosticsProviderLifecycle:
    """Construct diagnostics providers once for each active document-semantics mode.

    The owner contains optional-provider eligibility and spellcheck provider state,
    so refresh, display, and action code consume one authoritative service rather
    than reconstructing provider topology on their own paths.
    """

    def __init__(
        self,
        *,
        feature_profile: PromptFeatureProfileController,
        wildcard_feature: PromptWildcardDiagnosticProviderSource,
        document_semantics: PromptDocumentSemantics | None = None,
        conditioning_context: PromptConditioningContext | None = None,
        spellcheck_service: PromptSpellcheckService | None = None,
        service_factory: PromptDiagnosticsServiceFactory | None = None,
        spellcheck_provider_factory: PromptSpellcheckProviderFactory = (
            PromptSpellcheckDiagnosticProvider
        ),
    ) -> None:
        """Store provider capabilities without creating optional providers yet."""

        self._feature_profile = feature_profile
        self._wildcard_feature = wildcard_feature
        self._document_semantics = (
            document_semantics or OrdinaryPromptDocumentSemantics()
        )
        self._conditioning_context = (
            conditioning_context or unbound_prompt_conditioning_context()
        )
        self._spellcheck_service = spellcheck_service
        self._service_factory = (
            PromptDiagnosticsService if service_factory is None else service_factory
        )
        self._spellcheck_provider_factory = spellcheck_provider_factory
        self._service = PromptDiagnosticsService(())
        self._spellcheck_provider: PromptSpellcheckDiagnosticProvider | None = None
        self._active = False

    @property
    def is_active(self) -> bool:
        """Return whether the current provider topology is active."""

        return self._active

    @property
    def service(self) -> PromptDiagnosticsService:
        """Return the authoritative diagnostics service for refresh requests."""

        return self._service

    @property
    def spellcheck_provider(self) -> PromptSpellcheckDiagnosticProvider | None:
        """Return the active spellcheck provider for session-scoped actions."""

        return self._spellcheck_provider

    @property
    def document_semantics_identity(self) -> object:
        """Return the active document-semantics identity for published snapshots."""

        return self._document_semantics.identity

    @property
    def conditioning_context_identity(self) -> object:
        """Return graph context identity used by the active provider topology."""

        return self._conditioning_context.identity

    def can_activate(self) -> bool:
        """Return whether the configured feature set exposes any diagnostics."""

        return (
            (
                self._spellcheck_service is not None
                and self._feature_profile.spellcheck_enabled
            )
            or self._wildcard_feature.diagnostic_provider_ready()
            or self._feature_profile.duplicate_segment_diagnostics_enabled
            or not self._document_semantics.scenes_enabled
        )

    def activate(self) -> bool:
        """Build the initial provider topology and report whether activation occurred."""

        if self._active or not self.can_activate():
            return False
        self._rebuild_service()
        self._active = True
        return True

    def rebuild_for_document_semantics(self) -> bool:
        """Rebuild the active provider topology after document semantics changes."""

        if not self._active:
            return False
        self._rebuild_service()
        return True

    def replace_conditioning_context(
        self,
        conditioning_context: PromptConditioningContext,
    ) -> bool:
        """Replace graph context and rebuild active providers when identity changed."""

        if conditioning_context.identity == self._conditioning_context.identity:
            return False
        self._conditioning_context = conditioning_context
        if self._active:
            self._rebuild_service()
        return True

    def _rebuild_service(self) -> None:
        """Construct providers for the current feature and document-semantics state."""

        providers: list[PromptDiagnosticProvider] = [
            PromptUnsupportedSceneMarkerDiagnosticProvider(
                document_semantics=self._document_semantics
            )
        ]
        self._spellcheck_provider = None
        if (
            self._spellcheck_service is not None
            and self._feature_profile.spellcheck_enabled
        ):
            self._spellcheck_provider = self._spellcheck_provider_factory(
                self._spellcheck_service
            )
            providers.append(self._scoped_provider(self._spellcheck_provider))
        providers.extend(
            self._scoped_provider(provider)
            for provider in self._wildcard_feature.diagnostic_providers()
        )
        if self._feature_profile.duplicate_segment_diagnostics_enabled:
            providers.append(
                PromptDuplicateSegmentDiagnosticProvider(
                    document_semantics=self._document_semantics,
                    conditioning_context=self._conditioning_context,
                )
            )
        self._service = self._service_factory(tuple(providers))

    def _scoped_provider(
        self,
        provider: PromptDiagnosticProvider,
    ) -> PromptDiagnosticProvider:
        """Translate structured prompt values only for structured document semantics."""

        if not self._document_semantics.uses_structured_prompt_values:
            return provider
        return PromptStructuredValueDiagnosticProvider(
            provider=provider,
            document_semantics=self._document_semantics,
        )


__all__ = [
    "PromptDiagnosticsProviderLifecycle",
    "PromptDiagnosticsServiceFactory",
    "PromptSpellcheckProviderFactory",
]
