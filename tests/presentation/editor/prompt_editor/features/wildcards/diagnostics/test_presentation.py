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

"""Verify wildcard diagnostic presentation ownership."""

from __future__ import annotations

from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptWildcardDiagnosticPayload,
)
from substitute.domain.prompt.features.models import PromptEditorFeature

from ..support import wildcard_diagnostics_presentation


def test_wildcard_diagnostics_prepares_provider_when_syntax_enabled() -> None:
    """Wildcard diagnostics should be prepared by the wildcard feature owner."""

    controller = wildcard_diagnostics_presentation(
        (PromptEditorFeature.WILDCARD_SYNTAX,)
    )

    providers = controller.diagnostic_providers()

    assert controller.diagnostic_provider_ready() is True
    assert len(providers) == 1


def test_wildcard_diagnostics_disables_provider_without_wildcard_syntax() -> None:
    """Disabled wildcard syntax should prevent wildcard diagnostic providers."""

    controller = wildcard_diagnostics_presentation(())

    assert controller.diagnostic_provider_ready() is False
    assert controller.diagnostic_providers() == ()


def test_wildcard_diagnostics_prepares_missing_context_action() -> None:
    """Wildcard diagnostic actions should be owned by wildcard feature state."""

    controller = wildcard_diagnostics_presentation(
        (PromptEditorFeature.WILDCARD_SYNTAX,)
    )
    diagnostic = PromptDiagnostic(
        diagnostic_id="wildcard:0:9:simple:missing:",
        kind=PromptDiagnosticKind.WILDCARD,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=0,
        source_end=9,
        message="Missing wildcard: missing",
        payload=PromptWildcardDiagnosticPayload(
            identifier="missing",
            wildcard_form="simple",
        ),
    )

    actions = controller.actions_for_diagnostic(diagnostic)

    assert [action.label for action in actions] == ["Wildcard not found"]
    assert actions[0].callback_ready is False
    assert actions[0].disabled_reason == "missing_wildcard"
