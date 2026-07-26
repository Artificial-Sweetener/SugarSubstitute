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

"""Own wildcard diagnostics readiness and prepared diagnostic menu actions."""

from __future__ import annotations

from dataclasses import dataclass

from sugarsubstitute_shared.presentation.localization import app_text

from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.application.prompt_editor.diagnostics.coordinator import (
    PromptDiagnosticProvider,
)
from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
)
from substitute.application.prompt_editor.diagnostics.wildcard import (
    PromptWildcardDiagnosticProvider,
)

from .feature_profile_controller import PromptFeatureProfileController


@dataclass(frozen=True, slots=True)
class PromptWildcardContextAction:
    """Describe one wildcard-owned context action without binding to Qt widgets."""

    label: str
    callback_ready: bool = False
    disabled_reason: str | None = None


class PromptWildcardDiagnosticsPresentation:
    """Prepare wildcard diagnostic providers and menu actions from feature policy."""

    def __init__(
        self,
        *,
        feature_profile: PromptFeatureProfileController,
        wildcard_catalog_gateway: PromptWildcardCatalogGateway,
    ) -> None:
        """Store the feature policy and catalog gateway used by diagnostics."""

        self._feature_profile = feature_profile
        self._wildcard_catalog_gateway = wildcard_catalog_gateway

    def diagnostic_provider_ready(self) -> bool:
        """Return whether wildcard diagnostics should be included."""

        return self._feature_profile.wildcard_syntax_enabled

    def diagnostic_providers(self) -> tuple[PromptDiagnosticProvider, ...]:
        """Return wildcard diagnostic providers for diagnostics refresh."""

        if not self.diagnostic_provider_ready():
            return ()
        return (PromptWildcardDiagnosticProvider(self._wildcard_catalog_gateway),)

    def actions_for_diagnostic(
        self,
        diagnostic: PromptDiagnostic,
    ) -> tuple[PromptWildcardContextAction, ...]:
        """Return prepared context actions for one wildcard diagnostic."""

        if diagnostic.kind is not PromptDiagnosticKind.WILDCARD:
            return ()
        return (
            PromptWildcardContextAction(
                label=app_text("Wildcard not found"),
                callback_ready=False,
                disabled_reason="missing_wildcard",
            ),
        )


__all__ = ["PromptWildcardContextAction", "PromptWildcardDiagnosticsPresentation"]
