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

"""Test wildcard document diagnostic boundaries."""

from __future__ import annotations


from substitute.application.managed_text_assets.wildcard_csv_document_semantics import (
    WildcardCsvDocumentSemantics,
)
from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.application.prompt_editor.diagnostics.duplicate_segments import (
    PromptDuplicateSegmentDiagnosticProvider,
)
from substitute.application.prompt_editor.diagnostics.unsupported_scenes import (
    PromptUnsupportedSceneMarkerDiagnosticProvider,
)
from substitute.presentation.editor.prompt_editor.features.diagnostic_menu_actions import (
    actions_for_unsupported_scene_marker_diagnostic,
)


def test_txt_duplicate_diagnostics_do_not_cross_wildcard_candidates() -> None:
    """Duplicate tags should remain local to one TXT wildcard candidate."""

    provider = PromptDuplicateSegmentDiagnosticProvider(
        document_semantics=WildcardTextDocumentSemantics()
    )

    result = provider.diagnostics_for_text("red hair, blue eyes\nred hair, green eyes")

    assert result.diagnostics == ()


def test_txt_duplicate_diagnostics_still_report_within_one_candidate() -> None:
    """Duplicate tags inside one TXT wildcard candidate should remain errors."""

    provider = PromptDuplicateSegmentDiagnosticProvider(
        document_semantics=WildcardTextDocumentSemantics()
    )

    result = provider.diagnostics_for_text("red hair, red hair\nred hair, green eyes")

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.source_start == len("red hair, ")
    assert diagnostic.source_end == len("red hair, red hair")


def test_csv_duplicate_diagnostics_do_not_cross_data_cells() -> None:
    """Duplicate tags should remain local to one CSV wildcard value."""

    provider = PromptDuplicateSegmentDiagnosticProvider(
        document_semantics=WildcardCsvDocumentSemantics()
    )

    result = provider.diagnostics_for_text(
        'Name,Prompt\nfox,"red hair, blue eyes"\nwolf,"red hair, green eyes"'
    )

    assert result.diagnostics == ()


def test_csv_duplicate_diagnostics_still_report_within_one_data_cell() -> None:
    """Duplicate tags inside one quoted CSV value should remain errors."""

    source = 'Prompt\n"red hair, red hair"'
    provider = PromptDuplicateSegmentDiagnosticProvider(
        document_semantics=WildcardCsvDocumentSemantics()
    )

    result = provider.diagnostics_for_text(source)

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert source[diagnostic.source_start : diagnostic.source_end] == "red hair"
    assert diagnostic.source_start == source.rindex("red hair")


def test_ordinary_duplicate_diagnostics_preserve_whole_prompt_behavior() -> None:
    """Default duplicate diagnostics should preserve ordinary prompt behavior."""

    provider = PromptDuplicateSegmentDiagnosticProvider()

    result = provider.diagnostics_for_text("red hair\nred hair")

    assert len(result.diagnostics) == 1


def test_unsupported_scene_marker_provider_reports_exact_leading_marker_range() -> None:
    """Wildcard scene-marker diagnostics should underline exactly leading stars."""

    source = "  **Scene\nstars ** glitter"
    provider = PromptUnsupportedSceneMarkerDiagnosticProvider(
        document_semantics=WildcardTextDocumentSemantics()
    )

    result = provider.diagnostics_for_text(source)

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert source[diagnostic.source_start : diagnostic.source_end] == "**"
    assert diagnostic.message == "Scenes aren’t supported in wildcard values."


def test_unsupported_scene_marker_menu_explains_without_mutating_action() -> None:
    """Scene-marker menus should expose only the concise disabled explanation."""

    diagnostic = (
        PromptUnsupportedSceneMarkerDiagnosticProvider(
            document_semantics=WildcardTextDocumentSemantics()
        )
        .diagnostics_for_text("**Scene")
        .diagnostics[0]
    )

    actions = actions_for_unsupported_scene_marker_diagnostic(diagnostic)

    assert len(actions) == 1
    assert actions[0].label == "Scenes aren’t supported in wildcard values."
    assert actions[0].enabled is False
    assert actions[0].callback is None
