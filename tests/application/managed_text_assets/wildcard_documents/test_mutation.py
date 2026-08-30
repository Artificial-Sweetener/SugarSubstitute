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

"""Test wildcard document structured mutations."""

from __future__ import annotations


from substitute.application.managed_text_assets.wildcard_csv_document_parser import (
    parse_wildcard_csv_document,
)
from substitute.application.managed_text_assets.wildcard_csv_document_semantics import (
    WildcardCsvDocumentSemantics,
)
from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.application.prompt_editor.editing.structured_text import (
    PromptStructuredTextMutationService,
)
from substitute.application.prompt_editor.diagnostics.duplicate_mutations import (
    remove_duplicate_segment_edits,
)
from substitute.application.prompt_editor.diagnostics.models import (
    PromptDuplicateSegmentDiagnosticPayload,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptSetEmphasisWeightAction,
    PromptSetWildcardTagAction,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptEmphasisRendererView,
    PromptSyntaxService,
    PromptWildcardRendererView,
)
from substitute.application.prompt_editor.diagnostics.duplicate_segments import (
    PromptDuplicateSegmentDiagnosticProvider,
)
from substitute.domain.prompt.document.ranges import SourceRange
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)


def test_txt_wildcard_mutation_matches_ordinary_prompt_mutation() -> None:
    """TXT wildcard boundaries should not constrain ordinary syntax mutations."""

    source = "(Portrait:1.1), other\nplain"
    action = PromptSetEmphasisWeightAction(
        outer_start=0,
        outer_end=len("(Portrait:1.1)"),
        weight=1.2,
    )

    ordinary = PromptMutationService().apply_syntax_action(source, action)
    wildcard = PromptMutationService(
        document_semantics=WildcardTextDocumentSemantics()
    ).apply_syntax_action(source, action)

    assert wildcard == ordinary


def test_malformed_csv_text_mutation_fails_closed() -> None:
    """Malformed CSV should reject structured prompt-value mutations."""

    source = 'Name,Prompt\nfox,"unclosed'
    mutation_service = PromptStructuredTextMutationService(
        WildcardCsvDocumentSemantics()
    )

    replacement = mutation_service.replacement_for_range(
        source,
        SourceRange(source.index("fox"), source.index("fox") + 3),
        "wolf",
    )

    assert replacement is None


def test_csv_duplicate_mutation_preserves_cell_quoting() -> None:
    """Feature mutations inside quoted cells should leave CSV structure intact."""

    source = 'Prompt\n"red hair, red hair"'
    diagnostic = (
        PromptDuplicateSegmentDiagnosticProvider(
            document_semantics=WildcardCsvDocumentSemantics()
        )
        .diagnostics_for_text(source)
        .diagnostics[0]
    )
    payload = diagnostic.payload

    assert isinstance(payload, PromptDuplicateSegmentDiagnosticPayload)
    edit = remove_duplicate_segment_edits(source, payload)[0]
    updated = (
        source[: edit.source_start] + edit.replacement_text + source[edit.source_end :]
    )

    assert updated == 'Prompt\n"red hair"'
    assert parse_wildcard_csv_document(updated).valid is True


def test_csv_emphasis_mutation_uses_mapped_quoted_cell_ranges() -> None:
    """Emphasis actions should update quoted cell values without touching CSV quotes."""

    source = 'Prompt\n"(Value:1.1), other"'
    semantics = WildcardCsvDocumentSemantics()
    plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        document_semantics=semantics,
    ).build_render_plan(
        PromptDocumentService().build_document_view(source),
        PromptSyntaxProfile(enabled_syntaxes=("emphasis",)),
    )
    emphasis = plan.renderer_view_for_kind("emphasis")
    assert isinstance(emphasis, PromptEmphasisRendererView)
    span = emphasis.emphasis_spans[0]

    mutation = PromptMutationService(document_semantics=semantics).apply_syntax_action(
        source,
        PromptSetEmphasisWeightAction(
            outer_start=span.outer_start,
            outer_end=span.outer_end,
            weight=1.2,
        ),
    )

    assert mutation is not None
    assert mutation.text == 'Prompt\n"(Value:1.20), other"'
    assert parse_wildcard_csv_document(mutation.text).valid is True


def test_csv_wildcard_mutation_escapes_new_quotes_and_commas() -> None:
    """Wildcard tag edits should preserve valid quoting for structural characters."""

    source = 'Prompt\n"{animal}"'
    semantics = WildcardCsvDocumentSemantics()
    plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        document_semantics=semantics,
    ).build_render_plan(
        PromptDocumentService().build_document_view(source),
        PromptSyntaxProfile(enabled_syntaxes=("wildcard",)),
    )
    wildcard = plan.renderer_view_for_kind("wildcard")
    assert isinstance(wildcard, PromptWildcardRendererView)
    span = wildcard.wildcard_spans[0]

    mutation = PromptMutationService(document_semantics=semantics).apply_syntax_action(
        source,
        PromptSetWildcardTagAction(
            outer_start=span.outer_start,
            outer_end=span.outer_end,
            tag='group,"quoted"',
        ),
    )

    assert mutation is not None
    document = parse_wildcard_csv_document(mutation.text)
    assert document.valid is True
    assert document.records[1][0].quoted is True
    assert document.records[1][0].value == '{animal|group,"quoted"}'
