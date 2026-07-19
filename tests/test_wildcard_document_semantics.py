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

"""Test source-aligned wildcard prompt-value semantics."""

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
from substitute.application.prompt_editor.prompt_document_semantics import (
    OrdinaryPromptDocumentSemantics,
)
from substitute.application.prompt_editor.prompt_diagnostics_models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
)
from substitute.application.prompt_editor.prompt_diagnostics_service import (
    PromptDiagnosticProviderResult,
)
from substitute.application.prompt_editor.prompt_structured_value_diagnostic_provider import (
    PromptStructuredValueDiagnosticProvider,
)
from substitute.application.prompt_editor.prompt_structured_text_mutation_service import (
    PromptStructuredTextMutationService,
)
from substitute.application.prompt_editor.prompt_spellcheck_diagnostic_provider import (
    PromptSpellcheckDiagnosticProvider,
)
from substitute.application.prompt_editor.prompt_autocomplete_query_service import (
    PromptAutocompleteQueryService,
)
from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptEmphasisRendererView,
    PromptLoraRendererView,
    PromptMutationService,
    PromptSyntaxProfile,
    PromptSyntaxService,
    PromptWildcardRendererView,
    PromptReorderStateView,
    PromptDuplicateSegmentDiagnosticPayload,
    PromptSetEmphasisWeightAction,
    PromptSetWildcardTagAction,
    PromptSpellcheckCandidateService,
    PromptSpellcheckService,
    remove_duplicate_segment_edits,
)
from substitute.application.prompt_editor.prompt_duplicate_segment_diagnostic_provider import (
    PromptDuplicateSegmentDiagnosticProvider,
)
from substitute.application.prompt_editor.prompt_unsupported_scene_marker_diagnostic_provider import (
    PromptUnsupportedSceneMarkerDiagnosticProvider,
)
from substitute.domain.prompt import SourceRange
from substitute.presentation.editor.prompt_editor.features.diagnostic_menu_actions import (
    actions_for_unsupported_scene_marker_diagnostic,
)
from tests.prompt_projection_test_helpers import StaticPromptWildcardCatalogGateway


def test_ordinary_prompt_semantics_preserve_one_scene_capable_value() -> None:
    """Ordinary prompt semantics should preserve the existing whole prompt value."""

    semantics = OrdinaryPromptDocumentSemantics()

    mappings = semantics.value_mappings_for_text("first\n**Scene")

    assert semantics.scenes_enabled is True
    assert semantics.prompt_content_text("first\n**Scene") == "first\n**Scene"
    assert tuple(mapping.logical_text for mapping in mappings) == ("first\n**Scene",)
    assert semantics.unsupported_scene_marker_ranges("**Scene") == ()


def test_txt_wildcard_semantics_map_non_empty_candidate_lines() -> None:
    """TXT candidates should expose trimmed prompt-value mappings."""

    source = "  first, tag  \r\n\r\nsecond, tag\n"
    semantics = WildcardTextDocumentSemantics()

    mappings = semantics.value_mappings_for_text(source)

    assert semantics.scenes_enabled is False
    assert tuple(mapping.logical_text for mapping in mappings) == (
        "first, tag",
        "second, tag",
    )
    assert tuple(
        source[mapping.source_range.start : mapping.source_range.end]
        for mapping in mappings
    ) == ("first, tag", "second, tag")
    assert semantics.prompt_content_text(source) == source


def test_txt_wildcard_semantics_report_only_leading_scene_markers() -> None:
    """TXT validation should flag candidate-leading markers but not later stars."""

    source = "  **Scene\nstars ** glitter\n***Scene\n"

    marker_ranges = WildcardTextDocumentSemantics().unsupported_scene_marker_ranges(
        source
    )

    assert tuple(source[item.start : item.end] for item in marker_ranges) == (
        "**",
        "**",
    )
    assert tuple(item.start for item in marker_ranges) == (2, source.index("***Scene"))


def test_csv_parser_maps_quoted_commas_quotes_and_multiline_cells() -> None:
    """CSV parsing should retain exact ranges for decoded structured values."""

    source = 'Name,Prompt\r\nfox,"red, ""bright""\nforest"\r\nwolf,plain'

    document = parse_wildcard_csv_document(source)

    assert document.valid is True
    assert tuple(cell.value for cell in document.records[1]) == (
        "fox",
        'red, "bright"\nforest',
    )
    prompt_cell = document.records[1][1]
    assert source[prompt_cell.source_range.start] == '"'
    quote_index = prompt_cell.value.index('"')
    quote_range = prompt_cell.value_character_ranges[quote_index]
    assert source[quote_range.start : quote_range.end] == '""'


def test_csv_wildcard_semantics_exclude_headers_and_map_data_cells() -> None:
    """CSV mappings should include trimmed data cells without header values."""

    source = 'Name,Prompt\nfox,"  blue hair, green eyes  "\nwolf,red hair'

    mappings = WildcardCsvDocumentSemantics().value_mappings_for_text(source)

    assert tuple(mapping.logical_text for mapping in mappings) == (
        "fox",
        "blue hair, green eyes",
        "wolf",
        "red hair",
    )
    prompt_mapping = mappings[1]
    assert (
        source[prompt_mapping.source_range.start : prompt_mapping.source_range.end]
        == "blue hair, green eyes"
    )
    assert WildcardCsvDocumentSemantics().prompt_content_text(source) == (
        "fox\nblue hair, green eyes\nwolf\nred hair"
    )


def test_csv_wildcard_semantics_map_empty_data_cells_to_safe_anchors() -> None:
    """Empty CSV data cells should remain writable values without exposing headers."""

    source = 'First,Second\n,""'
    semantics = WildcardCsvDocumentSemantics()
    mappings = semantics.value_mappings_for_text(source)

    assert tuple(mapping.logical_text for mapping in mappings) == ("", "")
    assert tuple(mapping.source_range.start for mapping in mappings) == (
        source.index("\n") + 1,
        source.rindex('"'),
    )
    updated = semantics.replace_value_text(source, mappings[1].value_id, "value")
    assert updated == 'First,Second\n,"value"'


def test_csv_wildcard_semantics_find_markers_in_independent_cells() -> None:
    """CSV validation should find markers at decoded data-cell starts."""

    source = 'Name,Prompt\nfox," **Scene, forest"\nwolf,stars ** glitter'

    marker_ranges = WildcardCsvDocumentSemantics().unsupported_scene_marker_ranges(
        source
    )

    assert tuple(source[item.start : item.end] for item in marker_ranges) == ("**",)


def test_csv_wildcard_semantics_fail_closed_for_unclosed_quotes() -> None:
    """Malformed quoted CSV should expose no ambiguous prompt values."""

    semantics = WildcardCsvDocumentSemantics()

    assert semantics.value_mappings_for_text('Name,Prompt\nfox,"unclosed') == ()
    assert semantics.unsupported_scene_marker_ranges('Name,Prompt\nfox,"**Scene') == ()


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


def test_wildcard_autocomplete_never_creates_scene_queries() -> None:
    """Scene autocomplete should be absent under wildcard document semantics."""

    service = PromptAutocompleteQueryService(
        document_semantics=WildcardTextDocumentSemantics()
    )

    query = service.scene_autocomplete_query_at_cursor(
        text="**por",
        cursor_position=5,
        has_selection=False,
    )

    assert query is None


def test_txt_wildcard_autocomplete_matches_ordinary_non_scene_queries() -> None:
    """TXT wildcard boundaries should not isolate normal autocomplete queries."""

    source = "blue_ha\n{ani\n<lora:mod"
    document_view = PromptDocumentService().build_document_view(source)
    ordinary = PromptAutocompleteQueryService()
    wildcard = PromptAutocompleteQueryService(
        document_semantics=WildcardTextDocumentSemantics()
    )

    assert wildcard.autocomplete_query_at_cursor(
        document_view,
        text=source,
        cursor_position=len("blue_ha"),
        has_selection=False,
        minimum_prefix_length=1,
    ) == ordinary.autocomplete_query_at_cursor(
        document_view,
        text=source,
        cursor_position=len("blue_ha"),
        has_selection=False,
        minimum_prefix_length=1,
    )
    wildcard_position = source.index("{ani") + len("{ani")
    assert wildcard.wildcard_autocomplete_query_at_cursor(
        text=source,
        cursor_position=wildcard_position,
        has_selection=False,
    ) == ordinary.wildcard_autocomplete_query_at_cursor(
        text=source,
        cursor_position=wildcard_position,
        has_selection=False,
    )
    lora_position = len(source)
    assert wildcard.lora_autocomplete_query_at_cursor(
        text=source,
        cursor_position=lora_position,
        has_selection=False,
    ) == ordinary.lora_autocomplete_query_at_cursor(
        text=source,
        cursor_position=lora_position,
        has_selection=False,
    )


def test_csv_autocomplete_protects_headers_and_reads_decoded_values() -> None:
    """CSV autocomplete should operate on values without editing structure."""

    source = "Name,{Head\nfox,{ani"
    service = PromptAutocompleteQueryService(
        document_semantics=WildcardCsvDocumentSemantics()
    )

    header_query = service.wildcard_autocomplete_query_at_cursor(
        text=source,
        cursor_position=len("Name,{Head"),
        has_selection=False,
    )
    data_query = service.wildcard_autocomplete_query_at_cursor(
        text=source,
        cursor_position=len(source),
        has_selection=False,
    )

    assert header_query is None
    assert data_query is not None
    assert data_query.prefix == "ani"
    assert data_query.opener_start == source.rindex("{")


def test_csv_plain_autocomplete_decodes_quoted_values_and_maps_ranges() -> None:
    """Plain tag autocomplete should behave normally inside quoted CSV values."""

    source = 'Prompt\n"blue_ha, other"'
    value_start = source.index("blue_ha")
    cursor_position = value_start + len("blue_ha")
    service = PromptAutocompleteQueryService(
        document_semantics=WildcardCsvDocumentSemantics()
    )

    query = service.autocomplete_query_at_cursor(
        PromptDocumentService().build_document_view(source),
        text=source,
        cursor_position=cursor_position,
        has_selection=False,
        minimum_prefix_length=1,
    )

    assert query is not None
    assert query.prefix == "blue_ha"
    assert query.word_start == value_start
    assert query.word_end == cursor_position
    assert source[query.word_start : query.active_tag_end] == "blue_ha"


def test_csv_lora_autocomplete_decodes_escaped_quotes_and_maps_ranges() -> None:
    """LoRA autocomplete should ignore CSV encoding while preserving raw ranges."""

    source = 'Prompt\n"detail ""quoted"", <lora:mod"'
    cursor_position = source.index("mod") + len("mod")
    service = PromptAutocompleteQueryService(
        document_semantics=WildcardCsvDocumentSemantics()
    )

    query = service.lora_autocomplete_query_at_cursor(
        text=source,
        cursor_position=cursor_position,
        has_selection=False,
    )

    assert query is not None
    assert query.query_text == "mod"
    assert source[query.replacement_start : query.replacement_end] == "<lora:mod"


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

    assert tuple(diagnostic.message for diagnostic in result.diagnostics) == (
        "Possible spelling issue: mispelled",
    )
    diagnostic = result.diagnostics[0]
    assert source[diagnostic.source_start : diagnostic.source_end] == "mispelled"


def test_txt_reorder_retains_normal_cross_value_tag_behavior() -> None:
    """TXT wildcard values should share the normal tag reorder model."""

    source = "1girl, blonde hair, blue eyes\nsmile, red dress"
    service = PromptDocumentService()
    document_view = service.build_document_view(source)
    session = service.build_reorder_session_view(document_view)

    reordered = service.serialize_reorder_state_view(
        document_view,
        PromptReorderStateView(
            ordered_chip_indices=(0, 1, 3, 2, 4),
            separator_slots=session.reorder_state.separator_slots,
            has_trailing_comma=False,
        ),
    )

    assert tuple(chip.text for chip in session.chips) == (
        "1girl",
        "blonde hair",
        "blue eyes",
        "smile",
        "red dress",
    )
    assert reordered == ("1girl, blonde hair, smile\nblue eyes, red dress")


def test_csv_reorder_uses_normal_tags_and_preserves_value_containers() -> None:
    """CSV reorder should skip headers and encode tag movement into the same cells."""

    source = 'Prompt\n"1girl, blonde hair, blue eyes"\n"smile, red dress"'
    semantics = WildcardCsvDocumentSemantics()
    service = PromptDocumentService(document_semantics=semantics)
    document_view = service.build_document_view(source)
    session = service.build_reorder_session_view(document_view)
    state = PromptReorderStateView(
        ordered_chip_indices=(0, 1, 3, 2, 4),
        separator_slots=session.reorder_state.separator_slots,
        has_trailing_comma=False,
    )

    reordered = service.serialize_reorder_state_view(document_view, state)

    assert tuple(chip.text for chip in session.chips) == (
        "1girl",
        "blonde hair",
        "blue eyes",
        "smile",
        "red dress",
    )
    assert all(chip.text != "Prompt" for chip in session.chips)
    assert reordered == ('Prompt\n"1girl, blonde hair, smile"\n"blue eyes, red dress"')
    assert parse_wildcard_csv_document(reordered).valid is True


def test_csv_reorder_preserves_multiline_cells_and_column_boundaries() -> None:
    """Structured reorder should distinguish cell boundaries from value newlines."""

    source = 'Name,Prompt\nfox,"red hair,\nblue eyes"\nwolf,"smile, red dress"'
    semantics = WildcardCsvDocumentSemantics()
    service = PromptDocumentService(document_semantics=semantics)
    document_view = service.build_document_view(source)
    session = service.build_reorder_session_view(document_view)
    state = PromptReorderStateView(
        ordered_chip_indices=(0, 2, 1, 3, 4, 5),
        separator_slots=session.reorder_state.separator_slots,
        has_trailing_comma=False,
    )

    reordered = service.serialize_reorder_state_view(document_view, state)
    parsed = parse_wildcard_csv_document(reordered)

    assert tuple(chip.text for chip in session.chips) == (
        "fox",
        "red hair",
        "blue eyes",
        "wolf",
        "smile",
        "red dress",
    )
    assert parsed.valid is True
    assert parsed.records[1][0].value == "fox"
    assert parsed.records[1][1].value == "blue eyes,\nred hair"


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
