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

from substitute.application.prompt_editor.document.service import (
    PromptDocumentService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfileService,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
)
from substitute.application.prompt_editor.lora.resolution import (
    PromptLoraResolutionStatus,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptLoraRendererView,
    PromptSyntaxService,
)


from ..support.lora_catalog import (
    _BootstrapPromptLoraCatalogService,
    _FailingPromptLoraCatalogService,
    _StaticPromptLoraCatalogService,
    _StaticPromptWildcardCatalogGateway,
)


def test_prompt_syntax_service_builds_lora_renderer_view_when_enabled() -> None:
    """LoRA-enabled profiles should expose renderer-ready LoRA metadata."""

    model_page_url = "https://civitai.com/models/100?modelVersionId=200"
    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog_service = _StaticPromptLoraCatalogService(
        (
            PromptLoraCatalogItem(
                display_name="Sword stances collection [Pony]",
                display_subtitle="Battoujutsu",
                prompt_name=r"Illustrious\Character\Mineru",
                backend_value=r"Illustrious\Character\Mineru.safetensors",
                relative_path=r"Illustrious\Character\Mineru.safetensors",
                folder=r"Illustrious\Character",
                basename="Mineru",
                extension=".safetensors",
                thumbnail_variants=(),
                base_model="Illustrious",
                trained_words=("mineru",),
                tags=("character",),
                model_page_url=model_page_url,
                collision_key="mineru",
                collision_count=1,
                has_collision=False,
                search_text="mineru",
            ),
        )
    )
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog_service,
    )
    document_view = document_service.build_document_view(
        r"<lora:Illustrious\Character\Mineru:0.8>"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert [(span.kind, span.start, span.end) for span in render_plan.syntax_spans] == [
        ("lora", 0, len(document_view.source_text)),
    ]
    assert [
        (
            span.prompt_name,
            span.display_name,
            span.display_subtitle,
            span.first_weight_text,
            span.model_page_url,
            span.folder,
            span.base_model,
            span.has_collision,
        )
        for span in lora_view.lora_spans
    ] == [
        (
            r"Illustrious\Character\Mineru",
            "Sword stances collection [Pony]",
            "Battoujutsu",
            "0.8",
            model_page_url,
            r"Illustrious\Character",
            "Illustrious",
            False,
        )
    ]
    assert lora_catalog_service.calls == 1


def test_prompt_syntax_service_uses_fallback_lora_view_without_catalog() -> None:
    """Uncataloged LoRA syntax should still produce a LoRA renderer span."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(_StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(
        r"<lora:Illustrious\Character\Mineru:0.8>"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert [(span.kind, span.start, span.end) for span in render_plan.syntax_spans] == [
        ("lora", 0, len(document_view.source_text)),
    ]
    assert [
        (
            span.prompt_name,
            span.display_name,
            span.first_weight_text,
            span.backend_value,
            span.thumbnail_variants,
        )
        for span in lora_view.lora_spans
    ] == [
        (
            r"Illustrious\Character\Mineru",
            "Mineru",
            "0.8",
            None,
            (),
        )
    ]


def test_prompt_syntax_service_uses_fallback_lora_view_when_catalog_misses() -> None:
    """Missing catalog metadata should not remove parsed LoRA renderer spans."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog_service = _StaticPromptLoraCatalogService(())
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog_service,
    )
    document_view = document_service.build_document_view("<lora:failing_model:1>")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert len(lora_view.lora_spans) == 1
    assert lora_view.lora_spans[0].prompt_name == "failing_model"
    assert lora_view.lora_spans[0].display_name == "failing_model"
    assert lora_view.lora_spans[0].backend_value is None
    assert lora_catalog_service.calls == 1


def test_prompt_syntax_service_keeps_bootstrap_lora_misses_neutral() -> None:
    """Bootstrap catalog misses should not falsely mark LoRA chips as missing."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog_service = _BootstrapPromptLoraCatalogService(())
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog_service,
    )
    document_view = document_service.build_document_view("<lora:not_ready_yet:1>")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert lora_view.lora_spans[0].prompt_name == "not_ready_yet"
    assert lora_view.lora_spans[0].backend_value is None
    assert (
        lora_view.lora_spans[0].lora_status
        is PromptLoraResolutionStatus.PENDING_NO_AUTHORITY
    )
    assert lora_view.lora_spans[0].exists is True


def test_prompt_syntax_service_uses_fallback_lora_view_when_catalog_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Catalog lookup failures should log and degrade to fallback LoRA spans."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=_FailingPromptLoraCatalogService(),
    )
    document_view = document_service.build_document_view("<lora:missing_model:1>")

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    assert len(lora_view.lora_spans) == 1
    assert lora_view.lora_spans[0].prompt_name == "missing_model"
    assert lora_view.lora_spans[0].display_name == "missing_model"
    assert any(
        "LoRA catalog lookup failed; using fallback renderer span" in record.message
        for record in caplog.records
    )


def test_prompt_syntax_service_binds_unique_bare_lora_name_metadata() -> None:
    """Bare pasted LoRA schedules should bind unique catalog thumbnail metadata."""

    document_service = PromptDocumentService()
    profile_service = PromptSyntaxProfileService()
    lora_catalog_service = _StaticPromptLoraCatalogService(
        (
            PromptLoraCatalogItem(
                display_name="Ranni",
                display_subtitle=None,
                prompt_name=r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1",
                backend_value=(
                    r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1"
                    ".safetensors"
                ),
                relative_path=(
                    r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1"
                    ".safetensors"
                ),
                folder=r"illustrious\characters",
                basename="Ranni_illusXLNoobAI_Incrs_v1",
                extension=".safetensors",
                thumbnail_variants=(
                    PromptLoraThumbnailVariant(
                        size=512,
                        storage_key="RANNI:banner:512",
                        width=512,
                        height=44,
                        content_format="sqthumb-qimage-argb32-premultiplied",
                        byte_size=90112,
                    ),
                ),
                base_model="Illustrious",
                trained_words=("ranni",),
                tags=("character",),
                model_page_url=None,
                collision_key="ranni_illusxlnoobai_incrs_v1",
                collision_count=1,
                has_collision=False,
                search_text="ranni",
            ),
        )
    )
    syntax_service = PromptSyntaxService(
        _StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=lora_catalog_service,
    )
    document_view = document_service.build_document_view(
        "<lora:Ranni_illusXLNoobAI_Incrs_v1:1>"
    )

    render_plan = syntax_service.build_render_plan(
        document_view,
        profile_service.build_profile({"prompt_syntaxes": ["lora"]}),
    )
    lora_view = render_plan.renderer_view_for_kind("lora")

    assert isinstance(lora_view, PromptLoraRendererView)
    span = lora_view.lora_spans[0]
    assert span.prompt_name == "Ranni_illusXLNoobAI_Incrs_v1"
    assert span.display_name == "Ranni"
    assert span.folder == r"illustrious\characters"
    assert span.thumbnail_variants[0].storage_key == "RANNI:banner:512"
