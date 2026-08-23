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

"""Test wildcard document rendering and spellcheck mapping."""

from __future__ import annotations

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.managed_text_assets.wildcard_csv_document_semantics import (
    WildcardCsvDocumentSemantics,
)
from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
)
from substitute.application.prompt_editor.diagnostics.coordinator import (
    PromptDiagnosticProviderResult,
)
from substitute.application.prompt_editor.diagnostics.structured_values import (
    PromptStructuredValueDiagnosticProvider,
)
from substitute.application.prompt_editor.diagnostics.spellcheck_provider import (
    PromptSpellcheckDiagnosticProvider,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.diagnostics.spellcheck_candidates import (
    PromptSpellcheckCandidateService,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptEmphasisRendererView,
    PromptLoraRendererView,
    PromptSyntaxService,
    PromptWildcardRendererView,
)
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)


def test_wildcard_render_grouping_crosses_values_and_skips_csv_headers() -> None:
    """CSV decoding should retain normal document-wide wildcard grouping."""

    source = "{header}\n{animal},{animal}\n{animal},plain"
    semantics = WildcardCsvDocumentSemantics()
    document_view = PromptDocumentService().build_document_view(source)
    plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        document_semantics=semantics,
    ).build_render_plan(
        document_view,
        PromptSyntaxProfile(enabled_syntaxes=("wildcard",)),
    )

    renderer_view = plan.renderer_view_for_kind("wildcard")

    assert isinstance(renderer_view, PromptWildcardRendererView)
    assert tuple(span.identifier for span in renderer_view.wildcard_spans) == (
        "animal",
        "animal",
        "animal",
    )
    assert tuple(
        span.source_occurrence_count for span in renderer_view.wildcard_spans
    ) == (3, 3, 3)


def test_txt_wildcard_syntax_matches_ordinary_scene_free_rendering() -> None:
    """TXT wildcard values should retain ordinary document-wide syntax behavior."""

    source = "(Portrait:1.1), {animal}\n<lora:model:1>, {animal}"
    document_view = PromptDocumentService().build_document_view(source)
    syntax_profile = PromptSyntaxProfile(
        enabled_syntaxes=("emphasis", "wildcard", "lora")
    )
    gateway = StaticPromptWildcardCatalogGateway({})

    ordinary = PromptSyntaxService(gateway).build_render_plan(
        document_view,
        syntax_profile,
    )
    wildcard = PromptSyntaxService(
        gateway,
        document_semantics=WildcardTextDocumentSemantics(),
    ).build_render_plan(
        document_view,
        syntax_profile,
    )

    assert wildcard.syntax_spans == ordinary.syntax_spans
    assert wildcard.renderer_views == ordinary.renderer_views
    assert wildcard.document_semantics_identity == "wildcard-txt-v1"


def test_csv_rendering_filters_all_prompt_syntax_from_headers() -> None:
    """CSV headers should never render emphasis, wildcard, or LoRA syntax."""

    source = (
        '"(Header:1.2), {header}, <lora:header:1>"\n'
        '"(Value:1.1), {value}, <lora:value:1>"'
    )
    plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        document_semantics=WildcardCsvDocumentSemantics(),
    ).build_render_plan(
        PromptDocumentService().build_document_view(source),
        PromptSyntaxProfile(enabled_syntaxes=("emphasis", "wildcard", "lora")),
    )

    emphasis = plan.renderer_view_for_kind("emphasis")
    wildcard = plan.renderer_view_for_kind("wildcard")
    lora = plan.renderer_view_for_kind("lora")
    assert isinstance(emphasis, PromptEmphasisRendererView)
    assert isinstance(wildcard, PromptWildcardRendererView)
    assert isinstance(lora, PromptLoraRendererView)
    assert len(emphasis.emphasis_spans) == 1
    assert tuple(span.identifier for span in wildcard.wildcard_spans) == ("value",)
    assert tuple(span.prompt_name for span in lora.lora_spans) == ("value",)


def test_structured_diagnostics_decode_values_and_skip_csv_headers() -> None:
    """Structured diagnostics should map decoded values and protect headers."""

    source = "Header,Prompt\nfox,badword\nwolf,other"
    inner_provider = _StaticDiagnosticProvider()
    provider = PromptStructuredValueDiagnosticProvider(
        provider=inner_provider,
        document_semantics=WildcardCsvDocumentSemantics(),
    )

    result = provider.diagnostics_for_text(source)

    assert inner_provider.source_texts == ["fox", "badword", "wolf", "other"]
    assert tuple(diagnostic.message for diagnostic in result.diagnostics) == (
        "fox",
        "badword",
        "wolf",
        "other",
    )
    assert tuple(
        source[diagnostic.source_start : diagnostic.source_end]
        for diagnostic in result.diagnostics
    ) == ("fox", "badword", "wolf", "other")


def test_csv_spellcheck_parses_logical_values_and_skips_prompt_syntax() -> None:
    """Spellcheck should ignore headers and syntax inside quoted data cells."""

    source = 'Header\n"mispelled, {animal}, <lora:model:1>"'
    provider = PromptStructuredValueDiagnosticProvider(
        provider=PromptSpellcheckDiagnosticProvider(
            PromptSpellcheckService(
                gateway=_RejectAllSpellcheckGateway(),
                candidate_service=PromptSpellcheckCandidateService(),
            )
        ),
        document_semantics=WildcardCsvDocumentSemantics(),
    )

    result = provider.diagnostics_for_text(source)

    assert tuple(
        render_source_application_text(diagnostic.message)
        for diagnostic in result.diagnostics
    ) == ("Possible spelling issue: mispelled",)
    diagnostic = result.diagnostics[0]
    assert source[diagnostic.source_start : diagnostic.source_end] == "mispelled"


class _StaticDiagnosticProvider:
    """Return deterministic diagnostics for semantic filtering tests."""

    def __init__(self) -> None:
        """Prepare an empty record of logical source calls."""

        self.source_texts: list[str] = []

    def diagnostics_for_text(self, text: str) -> PromptDiagnosticProviderResult:
        """Return the configured diagnostics without inspecting source text."""

        self.source_texts.append(text)
        return PromptDiagnosticProviderResult(
            diagnostics=(_spelling_diagnostic(0, len(text), text),)
        )


def _spelling_diagnostic(start: int, end: int, word: str) -> PromptDiagnostic:
    """Build one spelling diagnostic at an exact source range."""

    return PromptDiagnostic(
        diagnostic_id=f"spelling:{start}:{end}",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=start,
        source_end=end,
        message=word,
        payload=PromptSpellingDiagnosticPayload(word=word),
    )


class _RejectAllSpellcheckGateway:
    """Reject every candidate while reporting an available spell backend."""

    def is_available(self) -> bool:
        """Report an available backend."""

        return True

    def availability_reason(self) -> str | None:
        """Return no unavailability reason."""

        return None

    def check_word(self, word: str) -> bool:
        """Reject every candidate word."""

        del word
        return False

    def suggest(self, word: str, *, limit: int = 8) -> tuple[str, ...]:
        """Return no replacement suggestions."""

        del word, limit
        return ()

    def supports_session_ignore(self) -> bool:
        """Report that session ignores are unavailable."""

        return False

    def ignore_for_session(self, word: str) -> None:
        """Reject unsupported session-ignore requests."""

        raise NotImplementedError(word)

    def supports_persistent_add(self) -> bool:
        """Report that persistent dictionary additions are unavailable."""

        return False

    def add_to_dictionary(self, word: str) -> bool:
        """Decline unsupported persistent dictionary additions."""

        del word
        return False
