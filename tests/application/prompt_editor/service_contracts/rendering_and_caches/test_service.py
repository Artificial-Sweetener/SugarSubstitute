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

import pytest

from substitute.application.prompt_editor.projection import (
    syntax_service as syntax_module,
)
from substitute.application.prompt_editor.document.service import (
    clear_prompt_document_caches,
    PromptDocumentService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfileService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    clear_prompt_syntax_render_plan_cache,
    PromptEmphasisRendererView,
    PromptLoraRendererView,
    PromptSyntaxService,
)
from substitute.application.prompt_editor.scenes.projection import (
    clear_prompt_scene_projection_cache,
    effective_prompt_text_at_source_position,
    parse_prompt_scene_projection_document,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    _lora_render_plan_summary,
)
from substitute.application.ports import (
    PromptWildcardResolution,
)


from ..support.lora_catalog import (
    _BootstrapPromptLoraCatalogService,
    _StaticPromptLoraCatalogService,
    _StaticPromptWildcardCatalogGateway,
    _lora_item,
)


def test_prompt_syntax_service_builds_renderer_ready_render_plan_without_reparsing() -> (
    None
):
    """Syntax service should build renderer views from an existing document view."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view("((cat:1.2) dog:1.1)")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.default_profile(),
    )
    emphasis_view = render_plan.renderer_view_for_kind("emphasis")

    assert [
        (span.kind, span.start, span.end, span.depth)
        for span in render_plan.syntax_spans
    ] == [  # noqa: E501
        ("emphasis", 0, 19, 0),
        ("emphasis", 1, 10, 1),
    ]
    assert isinstance(emphasis_view, PromptEmphasisRendererView)
    assert emphasis_view.kind == "emphasis"
    assert [
        (span.start, span.end, span.depth) for span in emphasis_view.syntax_spans
    ] == [
        (0, 19, 0),
        (1, 10, 1),
    ]
    assert [
        (span.content_start, span.content_end, span.depth)
        for span in emphasis_view.emphasis_spans
    ] == [
        (1, 14, 0),
        (2, 5, 1),
    ]


def test_prompt_document_service_reuses_cached_document_views() -> None:
    """Repeated prompt snapshots should reuse process-wide parse/view cache entries."""

    clear_prompt_document_caches()
    first_service = PromptDocumentService()
    second_service = PromptDocumentService()

    first_view = first_service.build_document_view("(cat:1.2), {animal}")
    second_view = second_service.build_document_view("(cat:1.2), {animal}")

    assert second_view is first_view


def test_prompt_scene_projection_service_reuses_cached_scene_documents() -> None:
    """Repeated scene projection parses should reuse the pure scene cache."""

    clear_prompt_scene_projection_cache()
    source = "quality\n**portrait\nportrait text"

    first_document = parse_prompt_scene_projection_document(source)
    second_document = parse_prompt_scene_projection_document(source)

    assert second_document is first_document


def test_effective_prompt_text_without_scenes_returns_full_text() -> None:
    """Scene-effective prompt context should preserve ordinary prompt text."""

    source = "quality, portrait"

    assert (
        effective_prompt_text_at_source_position(text=source, source_position=3)
        == source
    )


def test_effective_prompt_text_in_universal_block_uses_universal_text_only() -> None:
    """Scene-effective universal context should exclude all scene-local text."""

    source = "quality\n<lora:global:1>\n**portrait\nportrait text"

    assert (
        effective_prompt_text_at_source_position(
            text=source,
            source_position=source.index("quality"),
        )
        == "quality\n<lora:global:1>\n"
    )


def test_effective_prompt_text_inside_scene_materializes_universal_and_scene() -> None:
    """Scene-effective scene context should match generation materialization."""

    source = "quality\n<lora:global:1>\n**portrait\nportrait text\n**cafe\ncafe text"

    assert (
        effective_prompt_text_at_source_position(
            text=source,
            source_position=source.index("cafe text"),
        )
        == "quality\n<lora:global:1>\n\ncafe text"
    )


def test_effective_prompt_text_on_scene_marker_uses_that_scene() -> None:
    """Scene marker positions should resolve to their owning scene block."""

    source = "quality\n**portrait\nportrait text"

    assert (
        effective_prompt_text_at_source_position(
            text=source,
            source_position=source.index("**portrait"),
        )
        == "quality\n\nportrait text"
    )


def test_prompt_syntax_service_reuses_render_plan_until_catalog_revision_changes() -> (
    None
):
    """Syntax render-plan cache should avoid duplicate catalog work and invalidate by revision."""

    clear_prompt_syntax_render_plan_cache()
    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    gateway = _StaticPromptWildcardCatalogGateway(
        {
            ("animal", "simple", None): PromptWildcardResolution(
                identifier="animal",
                wildcard_form="simple",
                exists=True,
            ),
        }
    )
    syntax_service = PromptSyntaxService(gateway)
    document_view = document_service.build_document_view("{animal}, {animal}")
    profile = profile_service.build_profile({"prompt_syntaxes": ["wildcard"]})

    first_plan = syntax_service.build_render_plan(document_view, profile)
    second_plan = syntax_service.build_render_plan(document_view, profile)
    gateway.bump_revision()
    third_plan = syntax_service.build_render_plan(document_view, profile)

    assert second_plan is first_plan
    assert third_plan == first_plan
    assert third_plan is not first_plan
    assert len(gateway.calls) == 2


def test_prompt_syntax_service_invalidates_render_plan_on_lora_revision_change() -> (
    None
):
    """LoRA catalog revision changes should invalidate cached syntax render plans."""

    clear_prompt_syntax_render_plan_cache()
    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog = _StaticPromptLoraCatalogService(
        (
            _lora_item(
                display_name="Style",
                basename="style",
                prompt_name="style",
            ),
        )
    )
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog,
    )
    document_view = document_service.build_document_view("<lora:style:0.8>")
    profile = profile_service.build_profile({"prompt_syntaxes": ["lora"]})

    first_plan = syntax_service.build_render_plan(document_view, profile)
    second_plan = syntax_service.build_render_plan(document_view, profile)
    lora_catalog.bump_revision()
    third_plan = syntax_service.build_render_plan(document_view, profile)

    assert second_plan is first_plan
    assert third_plan == first_plan
    assert third_plan is not first_plan
    assert lora_catalog.calls == 2


def test_prompt_syntax_cache_separates_colliding_unversioned_catalog_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recycled object addresses must not reuse another catalog's render plan."""

    clear_prompt_syntax_render_plan_cache()
    document_view = PromptDocumentService().build_document_view("<lora:style:0.8>")
    profile = PromptSyntaxProfileService().build_profile({"prompt_syntaxes": ["lora"]})
    wildcard_gateway = _StaticPromptWildcardCatalogGateway({})
    empty_catalog = _StaticPromptLoraCatalogService(())
    populated_catalog = _StaticPromptLoraCatalogService(
        (
            _lora_item(
                display_name="Style",
                basename="style",
                prompt_name="style",
            ),
        )
    )
    del empty_catalog.cache_revision
    del populated_catalog.cache_revision
    real_id = id

    def colliding_id(value: object) -> int:
        """Give both unversioned test catalogs the same simulated address."""

        if isinstance(value, _StaticPromptLoraCatalogService):
            return 1
        return real_id(value)

    monkeypatch.setattr(syntax_module, "id", colliding_id, raising=False)

    empty_plan = PromptSyntaxService(
        wildcard_gateway,
        prompt_lora_catalog_service=empty_catalog,
    ).build_render_plan(document_view, profile)
    populated_plan = PromptSyntaxService(
        wildcard_gateway,
        prompt_lora_catalog_service=populated_catalog,
    ).build_render_plan(document_view, profile)

    assert populated_plan is not empty_plan
    populated_lora_view = populated_plan.renderer_view_for_kind("lora")
    assert isinstance(populated_lora_view, PromptLoraRendererView)
    assert populated_lora_view.lora_spans[0].exists is True


def test_prompt_syntax_service_lora_render_plan_summary_counts_resolution_states() -> (
    None
):
    """LoRA render-plan summaries should separate resolved and missing metadata."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog = _StaticPromptLoraCatalogService(
        (
            _lora_item(
                display_name="Style",
                basename="style",
                prompt_name="style",
            ),
        )
    )
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog,
    )
    document_view = document_service.build_document_view(
        "<lora:style:0.8>, <lora:missing:1.0>"
    )
    profile = profile_service.build_profile({"prompt_syntaxes": ["lora"]})

    render_plan = syntax_service.build_render_plan(document_view, profile)
    lora_view = render_plan.renderer_view_for_kind("lora")
    assert isinstance(lora_view, PromptLoraRendererView)
    summary = _lora_render_plan_summary(
        document_view=document_view,
        syntax_profile=profile,
        active_lora_syntax_spans=tuple(
            span for span in render_plan.syntax_spans if span.kind == "lora"
        ),
        lora_renderer_spans=tuple(lora_view.lora_spans),
        cache_revision=str(lora_catalog.cache_revision),
    )

    assert summary.document_lora_span_count == 2
    assert summary.active_lora_syntax_span_count == 2
    assert summary.renderer_lora_span_count == 2
    assert summary.resolved_lora_count == 1
    assert summary.missing_lora_count == 1
    assert summary.non_authoritative_unresolved_count == 0


def test_prompt_syntax_service_lora_summary_counts_bootstrap_unresolved() -> None:
    """Non-authoritative misses should stay separate from missing LoRAs."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog = _BootstrapPromptLoraCatalogService(())
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog,
    )
    document_view = document_service.build_document_view("<lora:missing:1.0>")
    profile = profile_service.build_profile({"prompt_syntaxes": ["lora"]})

    render_plan = syntax_service.build_render_plan(document_view, profile)
    lora_view = render_plan.renderer_view_for_kind("lora")
    assert isinstance(lora_view, PromptLoraRendererView)
    summary = _lora_render_plan_summary(
        document_view=document_view,
        syntax_profile=profile,
        active_lora_syntax_spans=tuple(
            span for span in render_plan.syntax_spans if span.kind == "lora"
        ),
        lora_renderer_spans=tuple(lora_view.lora_spans),
        cache_revision=str(lora_catalog.cache_revision),
    )

    assert summary.resolved_lora_count == 0
    assert summary.missing_lora_count == 0
    assert summary.non_authoritative_unresolved_count == 1
