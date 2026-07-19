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

"""Contract tests for prompt projection building from application prompt state."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptLoraCatalogItem,
    PromptLoraResolutionStatus,
    PromptLoraThumbnailVariant,
    PromptSyntaxService,
)
from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.application.ports import PromptWildcardResolution
from substitute.presentation.editor.prompt_editor.projection.builder import (
    _lora_projection_collapse_summary,
    _lora_renderer_view_for_plan,
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionCaretPlacement,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionRunKind,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
    PromptTransientNeutralEmphasisOwner,
)
from tests.prompt_projection_test_helpers import StaticPromptWildcardCatalogGateway
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile

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


def test_projection_builder_projects_scene_titles_without_marker_symbol() -> None:
    """Projected scene markers should hide `**` and expose bold title metadata."""

    projection = _build_projection("quality\n**portrait\nstudio portrait")

    scene_token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    )
    scene_run = next(
        run for run in projection.runs if run.token_id == scene_token.token_id
    )

    assert scene_token.display_text == "portrait"
    assert scene_token.content_range == (10, 18)
    assert scene_token.style_variant == "scene_title"
    assert scene_run.display_text == "portrait"
    assert scene_run.text_style_variant == "scene_title"
    assert "**portrait" not in projection.projection_text
    assert "portrait" in projection.projection_text


def test_projection_builder_keeps_scene_markers_literal_for_wildcard_documents() -> (
    None
):
    """Wildcard semantics should prevent scene-token projection entirely."""

    text = "**portrait\nstudio portrait"
    document_view = PromptDocumentService().build_document_view(text)
    render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({})
    ).build_render_plan(document_view, prompt_syntax_profile("emphasis", "wildcard"))

    projection = PromptProjectionBuilder(
        document_semantics=WildcardTextDocumentSemantics()
    ).build_projection(
        document_view,
        render_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
    )

    assert all(
        token.kind is not PromptProjectionTokenKind.SCENE for token in projection.tokens
    )
    assert "**portrait" in projection.projection_text


def test_projection_builder_classifies_only_local_scene_topology_changes() -> None:
    """Scene formation needs canonical projection while title growth does not."""

    builder = PromptProjectionBuilder()

    assert builder.source_edit_requires_canonical_rebuild("**", "**S", start=2, end=2)
    assert not builder.source_edit_requires_canonical_rebuild(
        "**S", "**Sc", start=3, end=3
    )
    assert not builder.source_edit_requires_canonical_rebuild(
        "plain\n**Scene", "plainer\n**Scene", start=5, end=5
    )
    assert builder.source_edit_requires_canonical_rebuild("**S", "**", start=2, end=3)
    assert builder.source_edit_requires_canonical_rebuild(
        "**Scene", "Scene", start=0, end=2
    )


def test_wildcard_projection_topology_ignores_literal_scene_markers() -> None:
    """Scene-disabled documents should retain literal incremental edit behavior."""

    builder = PromptProjectionBuilder(
        document_semantics=WildcardTextDocumentSemantics()
    )

    assert not builder.source_edit_requires_canonical_rebuild(
        "**", "**S", start=2, end=2
    )


def test_projection_builder_marks_duplicate_and_orphan_scene_titles_as_errors() -> None:
    """Invalid scene titles should carry only title-level error style metadata."""

    duplicate_projection = _build_projection("**portrait\none\n**Portrait\ntwo")
    duplicate_scene_tokens = [
        token
        for token in duplicate_projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    ]
    orphan_projection = _build_projection(
        "**hands\ndetail",
        scene_error_keys=frozenset({"hands"}),
    )
    orphan_scene_token = next(
        token
        for token in orphan_projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    )

    assert duplicate_scene_tokens[0].style_variant == "scene_title"
    assert duplicate_scene_tokens[1].style_variant == "scene_error"
    assert orphan_scene_token.style_variant == "scene_error"


def test_projection_builder_emits_projected_runs_for_emphasis_and_wildcard_tokens() -> (
    None
):
    """Projected mode should emit visible text runs plus inline-object runs."""

    projection = _build_projection(
        "(cat:1.05), {animal}",
        wildcard_resolutions={
            ("animal", "simple", None): PromptWildcardResolution(
                identifier="animal",
                wildcard_form="simple",
                exists=True,
            ),
        },
    )

    assert projection.projection_text.count(OBJECT_REPLACEMENT_CHARACTER) == 3
    assert [token.kind for token in projection.tokens] == [
        PromptProjectionTokenKind.EMPHASIS,
        PromptProjectionTokenKind.WILDCARD,
    ]
    assert [run.kind for run in projection.runs] == [
        PromptProjectionRunKind.INLINE_OBJECT,
        PromptProjectionRunKind.TEXT,
        PromptProjectionRunKind.INLINE_OBJECT,
        PromptProjectionRunKind.TEXT,
        PromptProjectionRunKind.INLINE_OBJECT,
    ]
    assert projection.runs[0].renderer_key == "emphasis_prefix"
    assert projection.runs[1].display_text == "cat"
    assert projection.runs[1].token_id == projection.tokens[0].token_id
    assert projection.runs[2].display_text == "1.05"
    assert projection.runs[2].renderer_key == "emphasis_suffix"
    assert projection.runs[4].display_text == "animal"
    assert projection.runs[4].renderer_key == "wildcard_chip"
    assert projection.tokens[0].display_text == "cat"
    assert projection.tokens[0].value_text == "1.05"
    assert projection.tokens[0].content_range == (1, 4)
    assert (
        projection.tokens[0].navigation_mode
        is PromptProjectionTokenNavigationMode.TEXT_CONTENT
    )
    assert projection.tokens[1].display_text == "animal"
    assert projection.tokens[1].status_text is None
    assert projection.tokens[1].wildcard_display_tag is None
    assert projection.tokens[1].wildcard_can_step_tag is False
    assert (
        projection.tokens[1].navigation_mode
        is PromptProjectionTokenNavigationMode.ATOMIC
    )


def test_projection_builder_projects_wildcard_group_tags_without_status_badges() -> (
    None
):
    """Projected wildcards should carry inline tag metadata without txt/csv labels."""

    projection = _build_projection("{animal}, {animal|2}, {animal|one}")

    wildcard_tokens = [
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.WILDCARD
    ]

    assert [
        (
            token.display_text,
            token.status_text,
            token.wildcard_display_tag,
            token.wildcard_tag_is_explicit,
            token.wildcard_can_step_tag,
        )
        for token in wildcard_tokens
    ] == [
        ("animal", None, "1", False, True),
        ("animal", None, "2", True, True),
        ("animal", None, "one", True, False),
    ]


def test_projection_builder_raw_mode_keeps_visible_runs_as_plain_source_text() -> None:
    """Raw mode should emit only text runs and preserve the source text verbatim."""

    projection = _build_projection(
        "(cat:1.05), {animal}",
        display_mode=PromptProjectionDisplayMode.RAW,
    )

    assert projection.display_mode is PromptProjectionDisplayMode.RAW
    assert projection.projection_text == "(cat:1.05), {animal}"
    assert len(projection.runs) == 1
    assert projection.runs[0].kind is PromptProjectionRunKind.TEXT
    assert projection.runs[0].display_text == "(cat:1.05), {animal}"


def test_projection_builder_plain_text_caret_map_exposes_all_source_boundaries() -> (
    None
):
    """Token-free single-run projections should keep exact plain caret stops."""

    projection = _build_projection("alpha beta")
    stops = projection.caret_map.stops

    assert projection.tokens == ()
    assert [stop.visual_index for stop in stops] == list(range(len(stops)))
    assert [stop.projection_position for stop in stops] == list(range(11))
    assert [stop.state.source_position for stop in stops] == list(range(11))
    assert {stop.state.placement for stop in stops} == {
        PromptProjectionCaretPlacement.PLAIN_TEXT
    }
    assert {stop.state.run_id for stop in stops} == {projection.runs[0].run_id}


def test_projection_builder_caret_map_builds_position_indexes_lazily() -> None:
    """Caret-map position dictionaries should be built only after lookup demand."""

    projection = _build_projection("alpha (cat:1.05) beta")
    caret_map = projection.caret_map

    assert caret_map._states_by_source_position is None  # noqa: SLF001
    assert caret_map._states_by_projection_position is None  # noqa: SLF001

    assert caret_map.state_for_source_position(0).source_position == 0
    assert caret_map._states_by_source_position is None  # noqa: SLF001
    assert caret_map._states_by_projection_position is None  # noqa: SLF001

    assert caret_map.state_for_projection_position(0).source_position == 0
    assert caret_map._states_by_source_position is None  # noqa: SLF001
    assert caret_map._states_by_projection_position is None  # noqa: SLF001

    caret_map._source_position_states()  # noqa: SLF001
    assert caret_map._states_by_source_position is not None  # noqa: SLF001
    assert caret_map._states_by_projection_position is None  # noqa: SLF001

    caret_map._projection_position_states()  # noqa: SLF001
    assert caret_map._states_by_projection_position is not None  # noqa: SLF001


def test_projection_builder_emits_projected_runs_for_lora_tokens() -> None:
    """Projected mode should collapse LoRA schedules into graphical chips."""

    projection = _build_projection(r"alpha, <lora:Illustrious\Character\Mineru:0.8>")

    assert [token.kind for token in projection.tokens] == [
        PromptProjectionTokenKind.LORA
    ]
    token = projection.tokens[0]
    assert token.display_text == "Sword stances collection [Pony]"
    assert token.lora_version_text == "Battoujutsu"
    assert token.value_text == "0.8"
    assert token.detail_text == r"Illustrious\Character\Mineru"
    assert token.model_page_url == _CIVITAI_MODEL_PAGE_URL
    assert token.status_text is None
    assert token.thumbnail_variants[0].role == BANNER_THUMBNAIL_ROLE
    assert token.navigation_mode is PromptProjectionTokenNavigationMode.ATOMIC
    assert projection.runs[-1].renderer_key == "lora_chip"
    assert projection.runs[-1].display_text == "Sword stances collection [Pony]"


def test_projection_builder_marks_uncataloged_lora_tokens_as_missing() -> None:
    """Unresolved inline LoRA syntax should stay projected but carry missing state."""

    projection = _build_projection(r"alpha, <lora:Unknown\Thing:0.8>")

    assert [token.kind for token in projection.tokens] == [
        PromptProjectionTokenKind.LORA
    ]
    token = projection.tokens[0]
    assert token.exists is False
    assert token.lora_status is PromptLoraResolutionStatus.MISSING
    assert token.status_text == "Not found"
    assert token.display_text == "Thing"
    assert token.detail_text == r"Unknown\Thing"
    assert token.lora_backend_value is None
    assert token.thumbnail_variants == ()


def test_projection_builder_skips_expanded_lora_tokens() -> None:
    """Expanded LoRA tokens should remain raw source instead of collapsing to chips."""

    text = r"alpha, <lora:Illustrious\Character\Mineru:0.8>"
    expanded_range = (7, len(text))
    projection = _build_projection(
        text,
        session=PromptProjectionSession(expanded_source_range=expanded_range),
    )

    assert [
        token.kind
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.LORA
    ] == []
    assert projection.projection_text == text


def test_lora_projection_collapse_summary_counts_expanded_skips() -> None:
    """LoRA projection summary should expose expanded-token skip counts."""

    text = r"alpha, <lora:Illustrious\Character\Mineru:0.8>"
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({}),
        prompt_lora_catalog_service=_StaticPromptLoraCatalogService(),
    )
    document_view = document_service.build_document_view(text)
    render_plan = syntax_service.build_render_plan(
        document_view,
        prompt_syntax_profile("lora"),
    )
    lora_view = _lora_renderer_view_for_plan(render_plan)
    expanded_range = (7, len(text))

    summary = _lora_projection_collapse_summary(
        document_view=document_view,
        render_plan=render_plan,
        all_supported_ranges=tuple(
            (span.start, span.end) for span in render_plan.syntax_spans
        ),
        lora_view=lora_view,
        lora_candidate_count=0,
        lora_skipped_expanded_count=1,
        lora_skipped_nested_count=0,
        expanded_source_range=expanded_range,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        candidates=(),
    )

    assert summary.renderer_lora_span_count == 1
    assert summary.lora_candidate_count == 0
    assert summary.lora_skipped_expanded_count == 1
    assert summary.lora_skipped_nested_count == 0
    assert summary.expanded_source_start == expanded_range[0]
    assert summary.expanded_source_end == expanded_range[1]
    assert summary.display_mode == "projected"
    assert summary.projected_lora_chip_count == 0


def test_projection_builder_projected_mode_hides_literal_parenthesis_escapes() -> None:
    """Projected mode should hide storage-only paren escapes in plain text runs."""

    projection = _build_projection(r"painting \(medium\)")

    assert projection.display_mode is PromptProjectionDisplayMode.PROJECTED
    assert projection.source_text == r"painting \(medium\)"
    assert projection.projection_text == "painting (medium)"
    assert projection.tokens == ()
    assert len(projection.runs) == 1
    assert projection.runs[0].kind is PromptProjectionRunKind.TEXT
    assert projection.runs[0].display_text == "painting (medium)"


def test_projection_builder_projects_escaped_weight_shape_as_literal_plain_text() -> (
    None
):
    """Escaped weighted-looking groups should stay plain visible text without tokens."""

    projection = _build_projection(r"\(painting:1.2\)")

    assert projection.projection_text == "(painting:1.2)"
    assert projection.tokens == ()
    assert len(projection.runs) == 1
    assert projection.runs[0].kind is PromptProjectionRunKind.TEXT
    assert projection.runs[0].display_text == "(painting:1.2)"


def test_projection_builder_raw_mode_preserves_literal_parenthesis_escapes_verbatim() -> (
    None
):
    """Raw mode should continue to expose the exact stored escaped source text."""

    projection = _build_projection(
        r"painting \(medium\)",
        display_mode=PromptProjectionDisplayMode.RAW,
    )

    assert projection.projection_text == r"painting \(medium\)"
    assert len(projection.runs) == 1
    assert projection.runs[0].display_text == r"painting \(medium\)"


def test_projection_builder_marks_active_tokens_and_respects_expanded_session_ranges() -> (
    None
):
    """Active tokens should be tagged, and expanded spans should remain raw source."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view("(cat:1.05), dog")
    render_plan = syntax_service.build_render_plan(
        document_view,
        prompt_syntax_profile("emphasis", "wildcard"),
    )
    builder = PromptProjectionBuilder()

    active_projection = builder.build_projection(
        document_view,
        render_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=(0, 10),
    )
    expanded_session = PromptProjectionSession(expanded_source_range=(0, 10))
    expanded_projection = builder.build_projection(
        document_view,
        render_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=expanded_session,
        active_span_range=(0, 10),
    )

    assert active_projection.tokens[0].active is True
    assert expanded_projection.tokens == ()
    assert expanded_projection.projection_text == "(cat:1.05), dog"


def test_projection_builder_marks_decorations_for_accent_feedback_ranges() -> None:
    """Builder should tag only requested syntax shells for decoration accent feedback."""

    projection = _build_projection(
        "(cat:1.05), {animal|1}, (dog:1.10)",
        decoration_accent_ranges=((0, 10), (12, 22)),
    )

    assert projection.tokens[0].decoration_accented is True
    assert projection.tokens[1].decoration_accented is True
    assert projection.tokens[2].decoration_accented is False


def test_projection_builder_adds_internal_emphasis_caret_stops_but_keeps_wildcards_atomic() -> (
    None
):
    """Caret-map construction should expose content stops only for emphasis tokens."""

    projection = _build_projection(
        "(cat:1.05), {animal}",
        wildcard_resolutions={
            ("animal", "simple", None): PromptWildcardResolution(
                identifier="animal",
                wildcard_form="simple",
                exists=True,
            ),
        },
    )

    emphasis_token = projection.tokens[0]
    wildcard_token = projection.tokens[1]
    emphasis_states = [
        stop.state
        for stop in projection.caret_map.stops
        if stop.state.token_id == emphasis_token.token_id
    ]
    wildcard_states = [
        stop.state
        for stop in projection.caret_map.stops
        if stop.state.token_id == wildcard_token.token_id
    ]

    assert [state.source_position for state in emphasis_states] == [0, 1, 2, 3, 4, 10]
    assert [state.source_position for state in wildcard_states] == [12, 20]


def test_projection_builder_can_project_transient_neutral_emphasis_without_source_syntax() -> (
    None
):
    """A transient neutral shell should project as emphasis while source text stays plain."""

    session = PromptProjectionSession()
    session.set_transient_neutral_emphasis(
        content_start=0,
        content_end=3,
        owner=PromptTransientNeutralEmphasisOwner.CARET,
    )

    projection = _build_projection("cat", session=session)

    assert projection.source_text == "cat"
    assert len(projection.tokens) == 1
    token = projection.tokens[0]
    assert token.kind is PromptProjectionTokenKind.EMPHASIS
    assert token.synthetic is True
    assert token.display_text == "cat"
    assert token.value_text == "1.00"
    assert token.content_range == (0, 3)
