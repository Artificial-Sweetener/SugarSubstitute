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

"""Contract tests for token-aware projection layout geometry and hit testing."""

from __future__ import annotations


from PySide6.QtGui import QColor, QFont

from substitute.presentation.editor.prompt_editor.projection.edit_to_frame import (
    PromptLayoutEditToFrameCoordinator,
)
from substitute.presentation.editor.prompt_editor.projection.metrics import (
    PromptProjectionMetricsFactory,
)
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from substitute.presentation.editor.prompt_editor.layout.canonical_builder import (
    PromptProjectionLineLayoutBuilder,
)
from substitute.presentation.editor.prompt_editor.layout.checkpoints import (
    capture_layout_checkpoint,
    restore_layout_checkpoint,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptProjectionInlineObjectRendererRegistry,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_document_for as _projection_for,
    projection_layout_for as _layout_for,
)

from .support import (
    _line_texts,
    _assert_line_fragments_match_current_runs,
    _layout_geometry_signature,
    _plain_text_wrap_width,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def test_projection_layout_reflow_rebuilds_only_the_dirty_line_window() -> None:
    """Wrap-changing middle edits should preserve prefix lines and exact geometry."""

    previous_text = ", ".join(f"tag {index} value" for index in range(240))
    edit_start = previous_text.index("tag 120") + len("tag 120")
    next_text = f"{previous_text[:edit_start]} extended{previous_text[edit_start:]}"
    incremental_layout, _ = _layout_for(previous_text, text_width=180.0)
    previous_first_line = incremental_layout.frame.output.snapshot.lines[0]  # noqa: SLF001
    next_document_view, next_projection = _projection_for(next_text)
    full_layout, _ = _layout_for(next_text, text_width=180.0)

    result = incremental_layout.set_projection_after_source_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text=" extended",
    )

    assert result.first_reflowed_line_index > 0
    assert incremental_layout.frame.output.snapshot.lines[0] is previous_first_line  # noqa: SLF001
    assert _layout_geometry_signature(incremental_layout) == _layout_geometry_signature(
        full_layout
    )


def test_projection_layout_reflows_before_changed_tag_keep_group() -> None:
    """Changing kept-tag eligibility should permit preceding-line backfill."""

    previous_text = "alpha, beta gamma delta, omega"
    edit_start = previous_text.index("beta") + len("beta")
    replacement_text = " extended"
    next_text = (
        f"{previous_text[:edit_start]}{replacement_text}{previous_text[edit_start:]}"
    )
    text_width = _plain_text_wrap_width("beta gamma delta,", "alpha, beta ")
    incremental_layout, _ = _layout_for(previous_text, text_width=text_width)
    next_document_view, next_projection = _projection_for(next_text)
    full_layout, _ = _layout_for(next_text, text_width=text_width)

    result = incremental_layout.set_projection_after_source_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_start,
        replacement_text=replacement_text,
    )

    assert result.first_reflowed_line_index == 0
    assert _line_texts(incremental_layout)[0] == "alpha, beta "
    assert _layout_geometry_signature(incremental_layout) == _layout_geometry_signature(
        full_layout
    )


def test_projection_layout_never_reuses_a_source_limited_terminal_line() -> None:
    """A probe boundary must not masquerade as deterministic suffix convergence."""

    text = "alpha beta gamma delta epsilon"
    document_view, projection = _projection_for(text)
    base_font = QFont()
    document_margin = 4.0
    text_width = 10_000.0
    metrics = PromptProjectionMetricsFactory().create(
        base_font=base_font,
        document_margin=document_margin,
        wrap_width=text_width,
    )
    line_builder = PromptProjectionLineLayoutBuilder(
        PromptProjectionInlineObjectRendererRegistry(())
    )
    probed_lines: list[PromptProjectionLineSnapshot] = []

    def record_probe(line: PromptProjectionLineSnapshot) -> int:
        """Record an invalid terminal probe and claim a reusable match."""

        probed_lines.append(line)
        return 0

    result = line_builder.build_snapshot_until_reusable_suffix(
        projection,
        wrap_width=text_width,
        base_font=base_font,
        document_margin=document_margin,
        content_left_inset=0.0,
        prompt_document_view=document_view,
        metrics=metrics,
        line_reuse_probe=record_probe,
        source_start=0,
        projection_start=0,
        line_top=metrics.initial_line_top(),
        source_limit=len("alpha beta"),
    )

    assert result.source_limited is True
    assert result.reusable_previous_line_index is None
    assert probed_lines == []


def test_projection_layout_fork_reflows_without_mutating_cached_source() -> None:
    """Copy-on-write preview reflow must preserve the cached source layout."""

    previous_text = "alpha\nbeta\ngamma"
    next_text = "beta\nalpha\ngamma"
    source_layout, _ = _layout_for(previous_text, text_width=180.0)
    source_signature = _layout_geometry_signature(source_layout)
    renderer_registry = source_layout.frame.output.configuration.inline_object_renderers
    fork = PromptLayoutEditToFrameCoordinator(renderer_registry)
    fork.frame.restore(source_layout.frame.output)
    assert fork.frame.output.configuration.inline_object_renderers is renderer_registry
    next_document_view, next_projection = _projection_for(next_text)
    full_layout, _ = _layout_for(next_text, text_width=180.0)

    fork.set_projection_after_source_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=0,
        edit_end=len("alpha\nbeta"),
        replacement_text="beta\nalpha",
    )

    assert source_layout.frame.output.projection_document.source_text == previous_text
    assert _layout_geometry_signature(source_layout) == source_signature
    assert _layout_geometry_signature(fork) == _layout_geometry_signature(full_layout)


def test_zero_delta_reused_suffix_rebinds_changed_projection_run_ids() -> None:
    """Same-size reorder previews must retain paintable suffix semantics."""

    suffix = "pink hair, long hair, twintails, (blue:1.35) ribbon"
    previous_text = f"alpha,\n\n(beta:1.20), gamma,\n\n{suffix}"
    replacement_text = "gamma, (beta:1.20),"
    edit_start = previous_text.index("(beta:1.20)")
    edit_end = edit_start + len("(beta:1.20), gamma,")
    next_text = previous_text[:edit_start] + replacement_text + previous_text[edit_end:]
    incremental_layout, previous_projection = _layout_for(
        previous_text,
        text_width=1000.0,
    )
    next_document_view, next_projection = _projection_for(next_text)
    full_layout, _ = _layout_for(next_text, text_width=1000.0)

    assert len(replacement_text) == edit_end - edit_start
    assert (
        next_projection.mapping.projection_length
        == previous_projection.mapping.projection_length
    )
    incremental_layout.set_projection_after_source_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
    )

    unresolved_fragments = tuple(
        fragment
        for line in incremental_layout.frame.output.snapshot.lines  # noqa: SLF001
        for fragment in line.fragments
        if incremental_layout.frame.paint_input.effective_run(fragment.run_id) is None
        or (
            fragment.token_id is not None
            and incremental_layout.frame.paint_input.effective_token(fragment.token_id)
            is None
        )
    )
    assert unresolved_fragments == ()
    assert _line_texts(incremental_layout) == _line_texts(full_layout)


def test_same_line_typing_refreshes_reused_suffix_fragment_semantics() -> None:
    """Typing after suffix reuse must keep every visible fragment paintable."""

    suffix = "pink hair, long hair, twintails, (blue:1.35) ribbon"
    previous_text = f"alpha,\n\n(beta:1.20), gamma,\n\n{suffix}"
    reordered_text = f"alpha,\n\ngamma, (beta:1.20),\n\n{suffix}"
    edit_start = previous_text.index("(beta:1.20)")
    edit_end = edit_start + len("(beta:1.20), gamma,")
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    reordered_view, reordered_projection = _projection_for(reordered_text)

    layout.set_projection_after_source_edit(
        reordered_projection,
        prompt_document_view=reordered_view,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text="gamma, (beta:1.20),",
    )

    typing_position = reordered_text.index("gamma") + len("gamma")
    typed_text = (
        f"{reordered_text[:typing_position]}X{reordered_text[typing_position:]}"
    )
    typed_view, typed_projection = _projection_for(typed_text)
    result = layout.try_apply_same_line_plain_text_edit(
        typed_projection,
        prompt_document_view=typed_view,
        edit_start=typing_position,
        edit_end=typing_position,
        replacement_text="X",
        first_dirty_projection_position=typing_position,
    )

    assert result.applied
    _assert_line_fragments_match_current_runs(
        layout,
        layout.frame.output.snapshot.lines[-1],  # noqa: SLF001
    )


def test_enter_refreshes_reused_suffix_fragment_semantics() -> None:
    """Enter after suffix reuse must keep downstream fragments paintable."""

    suffix = "pink hair, long hair, twintails, (blue:1.35) ribbon"
    previous_text = f"header text\nalpha,\n\n(beta:1.20), gamma,\n\n{suffix}"
    reordered_text = f"header text\nalpha,\n\ngamma, (beta:1.20),\n\n{suffix}"
    edit_start = previous_text.index("(beta:1.20)")
    edit_end = edit_start + len("(beta:1.20), gamma,")
    layout, _ = _layout_for(previous_text, text_width=1000.0)
    reordered_view, reordered_projection = _projection_for(reordered_text)
    layout.set_projection_after_source_edit(
        reordered_projection,
        prompt_document_view=reordered_view,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text="gamma, (beta:1.20),",
    )

    enter_position = len("header")
    entered_text = (
        f"{reordered_text[:enter_position]}\n{reordered_text[enter_position:]}"
    )
    entered_view, entered_projection = _projection_for(entered_text)
    result = layout.try_apply_hard_line_break_edit(
        entered_projection,
        prompt_document_view=entered_view,
        edit_start=enter_position,
        edit_end=enter_position,
        replacement_text="\n",
        first_dirty_projection_position=enter_position,
    )

    assert result.applied
    _assert_line_fragments_match_current_runs(
        layout,
        layout.frame.output.snapshot.lines[-1],  # noqa: SLF001
    )


def test_scene_title_remains_paintable_after_same_length_scene_body_reorder() -> None:
    """A body-only reorder must preserve the unchanged scene-title paint owner."""

    previous_text = "alpha, beta,\n\n**scene marker\ntest, test test, 1girl, fiksla"
    previous_body = "test, test test, 1girl, fiksla"
    replacement_text = "test, 1girl, fiksla, test test"
    edit_start = previous_text.index(previous_body)
    edit_end = edit_start + len(previous_body)
    next_text = previous_text[:edit_start] + replacement_text
    incremental_layout, _ = _layout_for(previous_text, text_width=1000.0)
    next_document_view, next_projection = _projection_for(next_text)
    full_layout, _ = _layout_for(next_text, text_width=1000.0)

    assert len(replacement_text) == edit_end - edit_start
    incremental_layout.set_projection_after_source_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text=replacement_text,
    )

    scene_fragments = tuple(
        fragment
        for line in incremental_layout.frame.output.snapshot.lines  # noqa: SLF001
        for fragment in line.fragments
        if isinstance(fragment, PromptProjectionTextFragment)
        and fragment.text == "scene marker"
    )
    assert len(scene_fragments) == 1
    assert (
        incremental_layout.frame.paint_input.effective_run(scene_fragments[0].run_id)
        is not None
    )
    assert _layout_geometry_signature(incremental_layout) == _layout_geometry_signature(
        full_layout
    )


def test_projection_layout_history_checkpoint_restores_only_matching_geometry() -> None:
    """History should restore shared layout exactly and reject stale width geometry."""

    initial_text = "alpha, (beta:1.20), gamma, delta"
    layout, _ = _layout_for(initial_text, text_width=180.0)
    initial_signature = _layout_geometry_signature(layout)
    paint_input = layout.frame.paint_input
    checkpoint = capture_layout_checkpoint(
        layout.frame.output,
        palette_key=int(paint_input.palette.cacheKey()),
        semantic_palette=paint_input.semantic_palette,
    )
    assert checkpoint is not None
    next_text = "alpha, inserted, (beta:1.20), gamma, delta"
    next_document_view, next_projection = _projection_for(next_text)
    layout.set_projection(next_projection, prompt_document_view=next_document_view)

    restored_output = restore_layout_checkpoint(
        checkpoint,
        configuration=layout.frame.output.configuration,
        palette_key=int(layout.frame.paint_input.palette.cacheKey()),
        semantic_palette=layout.frame.paint_input.semantic_palette,
    )
    assert restored_output is not None
    layout.frame.restore(restored_output)
    assert layout.frame.output.projection_document.source_text == initial_text
    assert _layout_geometry_signature(layout) == initial_signature

    layout.set_text_width(240.0)

    assert (
        restore_layout_checkpoint(
            checkpoint,
            configuration=layout.frame.output.configuration,
            palette_key=int(layout.frame.paint_input.palette.cacheKey()),
            semantic_palette=layout.frame.paint_input.semantic_palette,
        )
        is None
    )
    assert layout.frame.output.projection_document.source_text == initial_text
