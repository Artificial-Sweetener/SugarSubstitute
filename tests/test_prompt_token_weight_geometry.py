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

"""Cover prepared token-weight control geometry boundaries."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.overlays.token_weight_geometry import (
    PromptTokenWeightGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDisplayMode,
    PromptProjectionCaretMap,
    PromptProjectionDocument,
    PromptProjectionMapping,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)


def ensure_qapp() -> QApplication:
    """Return a running Qt application for geometry tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


class _FakeSurface(QWidget):
    """Provide deterministic projection geometry for token-weight tests."""

    def __init__(
        self,
        *,
        document: PromptProjectionDocument,
        anchors: dict[str, QRectF],
        weight_rects: dict[str, QRectF],
    ) -> None:
        """Create a fake projection surface with itself as the viewport."""

        super().__init__()
        self._document = document
        self._anchors = anchors
        self._weight_rects = weight_rects
        self.resize(320, 180)
        self.show()

    def viewport(self) -> QWidget:
        """Return the fake viewport widget."""

        return self

    def projection_document(self) -> PromptProjectionDocument:
        """Return the prepared projection document."""

        return self._document

    def token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the first token whose anchor contains the point."""

        for token in self._document.tokens:
            anchor = self._anchors.get(token.token_id)
            if anchor is not None and anchor.contains(position):
                return token
        return None

    def token_anchor_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the configured anchor for one token."""

        return self._anchors.get(token.token_id)

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the configured weight label rect for one token."""

        return self._weight_rects.get(token.token_id)


def _token(
    token_id: str,
    kind: PromptProjectionTokenKind,
    *,
    start: int,
    end: int,
    wildcard_can_step_tag: bool = False,
    synthetic: bool = False,
) -> PromptProjectionToken:
    """Return a minimal projection token for geometry tests."""

    return PromptProjectionToken(
        token_id=token_id,
        kind=kind,
        source_start=start,
        source_end=end,
        display_text=token_id,
        value_text="1.00",
        wildcard_display_tag="2"
        if kind is PromptProjectionTokenKind.WILDCARD
        else None,
        wildcard_can_step_tag=wildcard_can_step_tag,
        synthetic=synthetic,
        content_start=start + 1,
        content_end=max(start + 1, end - 1),
    )


def _document(
    tokens: tuple[PromptProjectionToken, ...],
    *,
    display_mode: PromptProjectionDisplayMode = PromptProjectionDisplayMode.PROJECTED,
) -> PromptProjectionDocument:
    """Return a minimal projection document for geometry tests."""

    return PromptProjectionDocument(
        display_mode=display_mode,
        source_text="",
        projection_text="",
        runs=(),
        tokens=tokens,
        mapping=PromptProjectionMapping(
            runs=(),
            source_length=0,
            projection_length=0,
        ),
        caret_map=PromptProjectionCaretMap(
            stops=(),
            tokens=tokens,
            source_length=0,
            projection_length=0,
        ),
    )


def _geometry(
    surface: _FakeSurface,
    host: QWidget,
) -> PromptTokenWeightGeometry:
    """Return a token-weight geometry owner with production control dimensions."""

    return PromptTokenWeightGeometry(
        surface,
        host=host,
        control_width=13.0,
        control_height=10.0,
        control_gap=0.5,
        control_margin=4.0,
        overlay_padding=2.0,
    )


def _host_and_surface(
    document: PromptProjectionDocument,
    *,
    anchors: dict[str, QRectF],
    weight_rects: dict[str, QRectF] | None = None,
) -> tuple[QWidget, _FakeSurface]:
    """Create visible host and fake surface widgets for coordinate mapping."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 260)
    surface = _FakeSurface(
        document=document,
        anchors=anchors,
        weight_rects={} if weight_rects is None else weight_rects,
    )
    surface.setParent(host)
    surface.move(30, 40)
    host.show()
    app.processEvents()
    return host, surface


def test_token_weight_geometry_prepares_emphasis_lora_wildcard_and_synthetic() -> None:
    """Eligible weighted token kinds produce prepared host-local geometry."""

    emphasis = _token("emphasis", PromptProjectionTokenKind.EMPHASIS, start=0, end=10)
    lora = _token("lora", PromptProjectionTokenKind.LORA, start=11, end=28)
    wildcard = _token(
        "wildcard",
        PromptProjectionTokenKind.WILDCARD,
        start=29,
        end=39,
        wildcard_can_step_tag=True,
    )
    synthetic = _token(
        "synthetic",
        PromptProjectionTokenKind.EMPHASIS,
        start=40,
        end=45,
        synthetic=True,
    )
    host, surface = _host_and_surface(
        _document((emphasis, lora, wildcard, synthetic)),
        anchors={
            "emphasis": QRectF(10, 12, 24, 12),
            "lora": QRectF(40, 12, 24, 12),
            "wildcard": QRectF(70, 12, 24, 12),
            "synthetic": QRectF(100, 12, 24, 12),
        },
    )

    snapshot = _geometry(surface, host).build_snapshot()

    assert tuple(item.token.token_id for item in snapshot.controls) == (
        "emphasis",
        "lora",
        "wildcard",
        "synthetic",
    )


def test_token_weight_geometry_omits_raw_mode_and_unsupported_wildcards() -> None:
    """Raw mode and nonnumeric wildcard tags produce no controls."""

    wildcard = _token(
        "wildcard",
        PromptProjectionTokenKind.WILDCARD,
        start=0,
        end=10,
        wildcard_can_step_tag=False,
    )
    raw_token = _token("emphasis", PromptProjectionTokenKind.EMPHASIS, start=11, end=20)
    host, surface = _host_and_surface(
        _document((wildcard, raw_token), display_mode=PromptProjectionDisplayMode.RAW),
        anchors={
            "wildcard": QRectF(10, 12, 24, 12),
            "emphasis": QRectF(40, 12, 24, 12),
        },
    )

    assert _geometry(surface, host).build_snapshot().controls == ()

    projected_host, projected_surface = _host_and_surface(
        _document((wildcard,)),
        anchors={"wildcard": QRectF(10, 12, 24, 12)},
    )
    assert _geometry(projected_surface, projected_host).build_snapshot().controls == ()


def test_token_weight_geometry_omits_tokens_with_missing_anchors() -> None:
    """Tokens without projection-owned anchors do not receive controls."""

    token = _token("emphasis", PromptProjectionTokenKind.EMPHASIS, start=0, end=10)
    host, surface = _host_and_surface(_document((token,)), anchors={})

    assert _geometry(surface, host).build_snapshot().controls == ()


def test_token_weight_geometry_maps_viewport_rects_into_host_coordinates() -> None:
    """Prepared anchors and weight rects are mapped from viewport to host space."""

    token = _token("emphasis", PromptProjectionTokenKind.EMPHASIS, start=0, end=10)
    host, surface = _host_and_surface(
        _document((token,)),
        anchors={"emphasis": QRectF(10, 20, 24, 12)},
        weight_rects={"emphasis": QRectF(30, 22, 18, 10)},
    )

    snapshot = _geometry(surface, host).build_snapshot()
    control = snapshot.controls[0]

    assert control.anchor_rect.topLeft() == QPointF(40, 60)
    assert control.anchor_rect.size() == QRectF(10, 20, 24, 12).size()
    assert control.weight_text_rect is not None
    assert control.weight_text_rect.topLeft() == QPointF(60, 62)
    assert snapshot.token_at_weight_viewport_position(QPointF(32, 24)) == token
    assert _geometry(surface, host).host_point_from_viewport_position(
        QPointF(10, 20)
    ) == QPointF(
        40,
        60,
    )


def test_token_weight_geometry_chooses_nearest_activation_zone() -> None:
    """Overlapping activation zones resolve to the nearest token anchor."""

    first = _token("first", PromptProjectionTokenKind.EMPHASIS, start=0, end=10)
    second = _token("second", PromptProjectionTokenKind.EMPHASIS, start=11, end=20)
    host, surface = _host_and_surface(
        _document((first, second)),
        anchors={
            "first": QRectF(10, 20, 24, 12),
            "second": QRectF(20, 20, 24, 12),
        },
    )
    snapshot = _geometry(surface, host).build_snapshot()

    selected = snapshot.geometry_at_pointer(QPointF(59, 66))

    assert selected is not None
    assert selected.token.token_id == "second"


def test_token_weight_geometry_overlay_bounds_include_padding() -> None:
    """Overlay bounds are padded around prepared host-local visible rects."""

    token = _token("emphasis", PromptProjectionTokenKind.EMPHASIS, start=0, end=10)
    host, surface = _host_and_surface(
        _document((token,)),
        anchors={"emphasis": QRectF(10, 20, 24, 12)},
        weight_rects={"emphasis": QRectF(30, 22, 18, 10)},
    )
    owner = _geometry(surface, host)
    control = owner.build_snapshot().controls[0]

    bounds = owner.overlay_bounds(
        (
            control.increase_rect,
            control.decrease_rect,
            control.weight_text_rect,
        )
    )

    assert bounds is not None
    assert control.weight_text_rect is not None
    assert bounds.contains(control.increase_rect)
    assert bounds.contains(control.decrease_rect)
    assert bounds.contains(control.weight_text_rect)
