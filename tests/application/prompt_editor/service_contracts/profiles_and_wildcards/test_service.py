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

"""Service-level tests for the prompt editor application layer."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import (
    PromptDocumentService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfileService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
    PromptWildcardRendererView,
)
from substitute.application.ports import (
    PromptWildcardReference,
    PromptWildcardResolution,
)


from ..support.lora_catalog import _StaticPromptWildcardCatalogGateway


def test_prompt_syntax_profile_service_uses_field_style_and_ignores_unknown_entries() -> (
    None
):
    """Profile resolution should read prompt_syntaxes from field style and ignore unknown values."""

    profile_service = PromptSyntaxProfileService()

    profile = profile_service.build_profile(
        {"prompt_syntaxes": ["wildcard", "unknown", "lora", "emphasis", "wildcard"]}
    )

    assert profile.enabled_syntaxes == ("wildcard", "lora", "emphasis")


def test_prompt_syntax_profile_service_falls_back_to_default_profile() -> None:
    """Missing or invalid prompt_syntaxes metadata should return the application default."""

    profile_service = PromptSyntaxProfileService()

    assert profile_service.build_profile({}).enabled_syntaxes == (
        "emphasis",
        "wildcard",
        "lora",
    )
    assert profile_service.build_profile(
        {"prompt_syntaxes": "wildcard"}
    ).enabled_syntaxes == ("emphasis", "wildcard", "lora")


def test_prompt_syntax_service_builds_wildcard_renderer_view_when_enabled() -> None:
    """Wildcard-enabled profiles should expose renderer-ready wildcard metadata."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    gateway = _StaticPromptWildcardCatalogGateway(
        {
            ("monster", "csv", "color"): PromptWildcardResolution(
                identifier="monster",
                wildcard_form="csv",
                csv_column="color",
                exists=True,
                matched_csv_column="Color",
                available_csv_columns=("Color", "Size"),
            ),
        }
    )
    syntax_service = PromptSyntaxService(gateway)
    document_view = document_service.build_document_view("{csv:monster:color}")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["emphasis", "wildcard"]}),
    )
    wildcard_view = render_plan.renderer_view_for_kind("wildcard")

    assert isinstance(wildcard_view, PromptWildcardRendererView)
    assert [(span.kind, span.start, span.end) for span in render_plan.syntax_spans] == [
        ("wildcard", 0, 19),
    ]
    assert [
        (
            span.identifier,
            span.wildcard_form,
            span.csv_column,
            span.exists,
            span.matched_csv_column,
            span.available_csv_columns,
            span.source_key,
            span.display_text,
            span.display_tag,
            span.tag_is_explicit,
            span.tag_is_numeric,
            span.can_step_tag,
            span.source_occurrence_count,
        )
        for span in wildcard_view.wildcard_spans
    ] == [
        (
            "monster",
            "csv",
            "color",
            True,
            "Color",
            ("Color", "Size"),
            "csv:monster",
            "monster:Color",
            None,
            False,
            False,
            False,
            1,
        ),
    ]
    assert gateway.calls == [
        (
            PromptWildcardReference(
                identifier="monster",
                wildcard_form="csv",
                csv_column="color",
            ),
        )
    ]


def test_prompt_syntax_service_classifies_numeric_wildcard_display_tags() -> None:
    """Only strict positive integer wildcard tags should support numeric stepping."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(
        "{one|1}, {two|2}, {twelve|12}, {zero|0}, {padded|01}, "
        "{negative|-1}, {decimal|1.5}, {word|one}, {mixed|a1}"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["wildcard"]}),
    )
    wildcard_view = render_plan.renderer_view_for_kind("wildcard")

    assert isinstance(wildcard_view, PromptWildcardRendererView)
    assert [
        (span.identifier, span.display_tag, span.tag_is_numeric, span.can_step_tag)
        for span in wildcard_view.wildcard_spans
    ] == [
        ("one", "1", True, True),
        ("two", "2", True, True),
        ("twelve", "12", True, True),
        ("zero", "0", False, False),
        ("padded", "01", False, False),
        ("negative", "-1", False, False),
        ("decimal", "1.5", False, False),
        ("word", "one", False, False),
        ("mixed", "a1", False, False),
    ]


def test_prompt_syntax_service_groups_wildcards_by_resolver_source() -> None:
    """Wildcard source grouping should ignore tags and CSV columns."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(
        "{monster}, {monster|2}, {csv:monster:color}, {csv:monster:size}"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["wildcard"]}),
    )
    wildcard_view = render_plan.renderer_view_for_kind("wildcard")

    assert isinstance(wildcard_view, PromptWildcardRendererView)
    assert [
        (span.identifier, span.csv_column, span.tag, span.source_key)
        for span in wildcard_view.wildcard_spans
    ] == [
        ("monster", None, None, "simple:monster"),
        ("monster", None, "2", "simple:monster"),
        ("monster", "color", None, "csv:monster"),
        ("monster", "size", None, "csv:monster"),
    ]
    assert [span.source_occurrence_count for span in wildcard_view.wildcard_spans] == [
        2,
        2,
        2,
        2,
    ]


def test_prompt_syntax_service_sets_implicit_and_explicit_wildcard_display_tags() -> (
    None
):
    """Repeated untagged sources should display implicit group tags without persistence."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))

    single_document_view = document_service.build_document_view("{monster}")
    repeated_document_view = document_service.build_document_view(
        "{monster}, {monster}"
    )
    explicit_document_view = document_service.build_document_view("{monster|one}")

    profile = profile_service.build_profile({"prompt_syntaxes": ["wildcard"]})
    single_view = syntax_service.build_render_plan(
        single_document_view,
        profile,
    ).renderer_view_for_kind("wildcard")
    repeated_view = syntax_service.build_render_plan(
        repeated_document_view,
        profile,
    ).renderer_view_for_kind("wildcard")
    explicit_view = syntax_service.build_render_plan(
        explicit_document_view,
        profile,
    ).renderer_view_for_kind("wildcard")

    assert isinstance(single_view, PromptWildcardRendererView)
    assert isinstance(repeated_view, PromptWildcardRendererView)
    assert isinstance(explicit_view, PromptWildcardRendererView)
    assert [
        (span.display_tag, span.tag_is_explicit, span.can_step_tag)
        for span in single_view.wildcard_spans
    ] == [(None, False, False)]
    assert [
        (span.display_tag, span.tag_is_explicit, span.can_step_tag)
        for span in repeated_view.wildcard_spans
    ] == [("1", False, True), ("1", False, True)]
    assert [
        (span.display_tag, span.tag_is_explicit, span.can_step_tag)
        for span in explicit_view.wildcard_spans
    ] == [("one", True, False)]


def test_prompt_syntax_service_omits_wildcard_renderers_when_profile_disables_them() -> (
    None
):
    """Wildcard spans should stay parsed but inactive when the field profile disables them."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    gateway = _StaticPromptWildcardCatalogGateway({})
    syntax_service = PromptSyntaxService(gateway)
    document_view = document_service.build_document_view("{animal}, (cat:1.05)")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["emphasis"]}),
    )

    assert [span.kind for span in document_view.syntax_spans] == [
        "wildcard",
        "emphasis",
    ]
    assert [span.kind for span in render_plan.syntax_spans] == ["emphasis"]
    assert render_plan.renderer_view_for_kind("wildcard") is None
    assert gateway.calls == []
