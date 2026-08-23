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

"""Real prompt projection builder fixtures for focused contracts."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.ports import PromptWildcardResolution
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)

_CIVITAI_MODEL_PAGE_URL = "https://civitai.com/models/100?modelVersionId=200"


class _StaticPromptLoraCatalogService:
    """Return deterministic LoRA catalog rows for projection tests."""

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return one cataloged LoRA row."""

        return (
            PromptLoraCatalogItem(
                display_name="Sword stances collection [Pony]",
                display_subtitle="Battoujutsu",
                prompt_name=r"Illustrious\Character\Mineru",
                backend_value=r"Illustrious\Character\Mineru.safetensors",
                relative_path=r"Illustrious\Character\Mineru.safetensors",
                folder=r"Illustrious\Character",
                basename="Mineru",
                extension=".safetensors",
                thumbnail_variants=(
                    PromptLoraThumbnailVariant(
                        size=768,
                        storage_key="MINERU:banner:768x160",
                        width=768,
                        height=160,
                        content_format="sqthumb-qimage-argb32-premultiplied",
                        byte_size=491520,
                        role=BANNER_THUMBNAIL_ROLE,
                    ),
                ),
                base_model="Illustrious",
                trained_words=("mineru",),
                tags=("character",),
                model_page_url=_CIVITAI_MODEL_PAGE_URL,
                collision_key="mineru",
                collision_count=1,
                has_collision=False,
                search_text="mineru",
            ),
        )

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return one cataloged LoRA row without simulating backend loading."""

        return self.list_loras()

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return one cataloged LoRA row when the prompt name matches it."""

        normalized_prompt_name = prompt_name.replace("\\", "/").casefold()
        for item in self.list_loras():
            if item.prompt_name.replace("\\", "/").casefold() == normalized_prompt_name:
                return item
        return None


def _build_projection(
    text: str,
    *,
    display_mode: PromptProjectionDisplayMode = PromptProjectionDisplayMode.PROJECTED,
    decoration_accent_ranges: tuple[tuple[int, int], ...] = (),
    scene_error_keys: frozenset[str] = frozenset(),
    session: PromptProjectionSession | None = None,
    wildcard_resolutions: dict[
        tuple[str, str, str | None],
        PromptWildcardResolution,
    ]
    | None = None,
) -> PromptProjectionDocument:
    """Build one prompt projection using the real document and syntax services."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway(wildcard_resolutions or {}),
        prompt_lora_catalog_service=_StaticPromptLoraCatalogService(),
    )
    document_view = document_service.build_document_view(text)
    render_plan = syntax_service.build_render_plan(
        document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    return PromptProjectionBuilder().build_projection(
        document_view,
        render_plan,
        display_mode=display_mode,
        session=PromptProjectionSession() if session is None else session,
        decoration_accent_ranges=decoration_accent_ranges,
        scene_error_keys=scene_error_keys,
    )
