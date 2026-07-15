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

"""Tests for reorder drag-proxy render-state lifecycle ownership."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxProfileService,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.reorder_drag_proxy_state import (
    PromptReorderDragProxyRenderInputs,
    PromptReorderDragProxyRenderStateBuilder,
)


class _EmptyPromptWildcardCatalogGateway:
    """Return deterministic missing wildcard rows for drag-proxy tests."""

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard suggestions."""

        _ = (prefix, limit)
        return ()

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return missing wildcard resolution rows."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=False,
            )
            for reference in references
        )


def _ensure_qapp() -> QApplication:
    """Return a running Qt application for font and palette ownership."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _builder() -> PromptReorderDragProxyRenderStateBuilder:
    """Return a drag-proxy render-state owner with deterministic services."""

    return PromptReorderDragProxyRenderStateBuilder(
        document_service=PromptDocumentService(),
        syntax_service=PromptSyntaxService(_EmptyPromptWildcardCatalogGateway()),
        syntax_profile=PromptSyntaxProfileService().default_profile(),
    )


def _inputs(
    *,
    font: QFont | None = None,
    source_revision: int | None = 1,
) -> PromptReorderDragProxyRenderInputs:
    """Return one complete proxy input snapshot for cache tests."""

    app = _ensure_qapp()
    return PromptReorderDragProxyRenderInputs(
        segment_index=2,
        segment_text="(alpha:1.1)",
        source_revision=source_revision,
        fill_color=QColor("#203040"),
        border_color=QColor("#405060"),
        font=font or app.font(),
        palette=app.palette(),
    )


def _counter(
    builder: PromptReorderDragProxyRenderStateBuilder,
    name: str,
) -> int:
    """Return one integer lifecycle counter from the builder."""

    return builder.counters()[name]


def test_drag_proxy_render_state_reuses_same_inputs() -> None:
    """Repeated visible use with identical inputs should reuse render state."""

    builder = _builder()
    builder.reset_drag_session()
    inputs = _inputs()

    first = builder.ensure_render_state(inputs)
    second = builder.ensure_render_state(inputs)

    assert first.rebuilt is True
    assert second.rebuilt is False
    assert second.render_state is first.render_state
    assert _counter(builder, "drag_proxy_render_state_rebuild_count") == 1
    assert _counter(builder, "drag_proxy_render_state_reuse_count") == 1


def test_drag_proxy_render_state_rebuilds_after_explicit_invalidation() -> None:
    """Explicit invalidation should force one rebuild for the next visible use."""

    builder = _builder()
    builder.reset_drag_session()
    inputs = _inputs()

    first = builder.ensure_render_state(inputs)
    builder.invalidate(reason="font_change")
    second = builder.ensure_render_state(inputs)

    assert first.rebuilt is True
    assert second.rebuilt is True
    assert second.render_state is not first.render_state
    assert _counter(builder, "drag_proxy_render_state_rebuild_count") == 2
    assert _counter(builder, "drag_proxy_render_state_invalidation_count") == 1


def test_drag_proxy_render_state_key_includes_source_revision_and_font() -> None:
    """Source and font identities should rebuild stale proxy render state."""

    app = _ensure_qapp()
    builder = _builder()
    builder.reset_drag_session()
    font = app.font()
    changed_font = QFont(font)
    changed_font.setPointSize(font.pointSize() + 2)

    builder.ensure_render_state(_inputs(font=font, source_revision=1))
    source_changed = builder.ensure_render_state(
        _inputs(font=font, source_revision=2),
    )
    font_changed = builder.ensure_render_state(
        _inputs(font=changed_font, source_revision=2),
    )

    assert source_changed.rebuilt is True
    assert font_changed.rebuilt is True
    assert _counter(builder, "drag_proxy_render_state_rebuild_count") == 3
