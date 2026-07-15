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

"""Render semantic Danbooru inline content with native chip-aware wrapping."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re
from urllib.parse import quote, unquote

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QContextMenuEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from substitute.application.danbooru import (
    DanbooruWikiCodeNode,
    DanbooruWikiExternalLinkNode,
    DanbooruWikiInlineNode,
    DanbooruWikiLineBreakNode,
    DanbooruWikiSearchLinkNode,
    DanbooruWikiTagChipNode,
    DanbooruWikiTextNode,
    DanbooruWikiWikiLinkNode,
    plain_text_from_inline_nodes,
    prompt_display_text_from_tag,
)
from substitute.presentation.danbooru.wiki_tag_chip import (
    tag_chip_palette_for_category,
)
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

_TOKEN_SPLIT_PATTERN = re.compile(r"\S+|\s+")
_WIKI_SCHEME_PREFIX = "danbooru-wiki:"
_BASE_FONT_POINT_SIZE = 10.0
_CAPTION_FONT_POINT_SIZE = 9.0
_LINE_GAP = 6.0
_TEXT_COLOR_DARK = QColor("#f2f2f2")
_TEXT_COLOR_LIGHT = QColor("#1b1b1b")
_MUTED_LINK_COLOR_DARK = QColor("#ff8fc0")
_MUTED_LINK_COLOR_LIGHT = QColor("#c12f73")
_CODE_BACKGROUND_DARK = QColor(127, 127, 127, 34)
_CODE_BACKGROUND_LIGHT = QColor(127, 127, 127, 24)
_CODE_BORDER_DARK = QColor(255, 255, 255, 24)
_CODE_BORDER_LIGHT = QColor(0, 0, 0, 20)
_CODE_PADDING_X = 4.0
_CODE_PADDING_Y = 2.0
_CODE_RADIUS = 4.0
_CHIP_PADDING_X = 8.0
_CHIP_PADDING_Y = 2.0
_CHIP_RADIUS = 10.0
_TEXT_LINE_PADDING_Y = 2.0
_COPY_TAG_ACTION_TEXT = "Copy tag"
_OPEN_IN_BROWSER_ACTION_TEXT = "Open in browser"
_DANBOORU_WIKI_PAGE_BASE_URL = "https://danbooru.donmai.us/wiki_pages/"


@dataclass(frozen=True, slots=True)
class _InlineStyle:
    """Carry the inherited inline style for one semantic node traversal."""

    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    link_target: str | None = None
    code: bool = False


@dataclass(frozen=True, slots=True)
class _InlineToken:
    """Describe one layout token that the inline flow widget can paint."""

    kind: str
    text: str
    style: _InlineStyle
    category_name: str | None = None


@dataclass(frozen=True, slots=True)
class _PaintToken:
    """Capture one measured token at a concrete position."""

    token: _InlineToken
    rect: QRectF
    font: QFont
    text_rect: QRectF


@dataclass(frozen=True, slots=True)
class _MeasuredToken:
    """Capture token metrics needed for baseline-aligned line layout."""

    token: _InlineToken
    font: QFont
    rect: QRectF
    text_rect: QRectF
    ascent: float
    descent: float
    top_padding: float
    bottom_padding: float

    @property
    def width(self) -> float:
        """Return the outer token width."""

        return self.rect.width()

    @property
    def height(self) -> float:
        """Return the outer token height."""

        return self.rect.height()

    @property
    def baseline_ascent(self) -> float:
        """Return the token height above the shared line baseline."""

        return self.top_padding + self.ascent

    @property
    def baseline_descent(self) -> float:
        """Return the token height below the shared line baseline."""

        return self.bottom_padding + self.descent


class DanbooruWikiInlineFlow(QWidget):
    """Render semantic Danbooru inline content with native wrapping and chips."""

    linkActivated = Signal(str)

    def __init__(
        self,
        *,
        inline_nodes: tuple[DanbooruWikiInlineNode, ...],
        compact: bool = False,
        open_url: Callable[[str], bool] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build one native inline flow from semantic inline nodes."""

        super().__init__(parent)
        self._inline_nodes = inline_nodes
        self._compact = compact
        self._open_url = open_url
        self._plain_text = plain_text_from_inline_nodes(inline_nodes)
        self._layout_cache: dict[int, tuple[tuple[_PaintToken, ...], float]] = {}
        self._hover_target: str | None = None
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def plain_text(self) -> str:
        """Return flattened plain text for diagnostics and widget tests."""

        return self._plain_text

    def link_targets(self) -> tuple[str, ...]:
        """Return all unique interactive targets for diagnostics and tests."""

        return tuple(
            dict.fromkeys(
                token.token.style.link_target
                for token in self._layout_for_width(self.width())[0]
                if token.token.style.link_target is not None
            )
        )

    def hasHeightForWidth(self) -> bool:
        """Return whether the widget computes height from the assigned width."""

        return True

    def heightForWidth(self, width: int) -> int:
        """Return the preferred height for one available render width."""

        _, total_height = self._layout_for_width(width)
        return max(1, round(total_height))

    def minimumSizeHint(self) -> QSize:
        """Return a stable minimum size for layout negotiation."""

        return QSize(120, self.heightForWidth(120))

    def sizeHint(self) -> QSize:
        """Return the preferred size for one inline flow widget."""

        return QSize(240, self.heightForWidth(240))

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the inline text, links, code runs, and native chip tokens."""

        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        is_dark = _is_dark_palette(self)
        default_text_color = _TEXT_COLOR_DARK if is_dark else _TEXT_COLOR_LIGHT
        link_color = _MUTED_LINK_COLOR_DARK if is_dark else _MUTED_LINK_COLOR_LIGHT
        code_background = _CODE_BACKGROUND_DARK if is_dark else _CODE_BACKGROUND_LIGHT
        code_border = _CODE_BORDER_DARK if is_dark else _CODE_BORDER_LIGHT

        tokens, _ = self._layout_for_width(self.width())
        for paint_token in tokens:
            token = paint_token.token
            if token.kind == "space":
                continue
            if token.kind == "chip":
                palette = tag_chip_palette_for_category(
                    token.category_name,
                    is_dark=is_dark,
                )
                painter.setBrush(palette.fill_color)
                painter.setPen(_stroke_pen(palette.border_color))
                painter.drawRoundedRect(
                    _aligned_stroke_rect(paint_token.rect),
                    _CHIP_RADIUS,
                    _CHIP_RADIUS,
                )
                painter.setFont(paint_token.font)
                painter.setPen(palette.text_color)
                painter.drawText(
                    paint_token.text_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    token.text,
                )
                continue
            if token.style.code:
                painter.setBrush(code_background)
                painter.setPen(_stroke_pen(code_border))
                painter.drawRoundedRect(
                    _aligned_stroke_rect(paint_token.rect),
                    _CODE_RADIUS,
                    _CODE_RADIUS,
                )
            painter.setFont(paint_token.font)
            painter.setPen(
                link_color if token.style.link_target else default_text_color
            )
            painter.drawText(
                paint_token.text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                token.text,
            )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Refresh the pointer cursor when the hover target changes."""

        hover_target = self._target_at_position(event.position())
        if hover_target == self._hover_target:
            super().mouseMoveEvent(event)
            return
        self._hover_target = hover_target
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if hover_target is not None
            else Qt.CursorShape.ArrowCursor
        )
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        """Restore the normal pointer cursor when the hover leaves the widget."""

        self._hover_target = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit the clicked target when one interactive token is released."""

        if event.button() is Qt.MouseButton.LeftButton:
            target = self._target_at_position(event.position())
            if target is not None:
                self.linkActivated.emit(target)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Show chip-specific actions when a tag chip is right-clicked."""

        chip_token = self._chip_token_at_position(event.pos())
        if chip_token is None:
            event.ignore()
            return
        self._show_chip_context_menu(chip_token=chip_token, event=event)

    def _layout_for_width(self, width: int) -> tuple[tuple[_PaintToken, ...], float]:
        """Return the cached paint layout for one available render width."""

        bounded_width = max(1, width)
        cached = self._layout_cache.get(bounded_width)
        if cached is not None:
            return cached
        layout = self._build_layout(bounded_width)
        self._layout_cache[bounded_width] = layout
        return layout

    def _build_layout(self, width: int) -> tuple[tuple[_PaintToken, ...], float]:
        """Measure and place tokens for one target render width."""

        max_width = max(1.0, float(width))
        tokens = _tokens_from_nodes(self._inline_nodes)
        paint_tokens: list[_PaintToken] = []
        line_tokens: list[tuple[_MeasuredToken, float]] = []
        line_width = 0.0
        y = 0.0
        for token in tokens:
            if token.kind == "linebreak":
                paint_tokens.extend(
                    self._place_line_tokens(line_tokens=line_tokens, y=y)
                )
                y += _line_height(line_tokens) + _LINE_GAP
                line_tokens = []
                line_width = 0.0
                continue
            measured = self._measure_token(token)
            if token.kind == "space":
                if line_width <= 0.0:
                    continue
                if line_width + measured.width > max_width:
                    paint_tokens.extend(
                        self._place_line_tokens(line_tokens=line_tokens, y=y)
                    )
                    y += _line_height(line_tokens) + _LINE_GAP
                    line_tokens = []
                    line_width = 0.0
                    continue
                line_tokens.append((measured, line_width))
                line_width += measured.width
                continue

            if line_width > 0.0 and line_width + measured.width > max_width:
                paint_tokens.extend(
                    self._place_line_tokens(line_tokens=line_tokens, y=y)
                )
                y += _line_height(line_tokens) + _LINE_GAP
                line_tokens = []
                line_width = 0.0
            line_tokens.append((measured, line_width))
            line_width += measured.width

        if line_tokens:
            paint_tokens.extend(self._place_line_tokens(line_tokens=line_tokens, y=y))
            total_height = y + _line_height(line_tokens)
        else:
            total_height = max(1.0, float(self.fontMetrics().height()))
        return tuple(paint_tokens), total_height

    def _place_line_tokens(
        self,
        *,
        line_tokens: list[tuple[_MeasuredToken, float]],
        y: float,
    ) -> tuple[_PaintToken, ...]:
        """Return one line of tokens placed against a shared baseline."""

        if not line_tokens:
            return ()
        baseline = y + max(measured.baseline_ascent for measured, _ in line_tokens)
        placed: list[_PaintToken] = []
        for measured, x in line_tokens:
            top = baseline - measured.baseline_ascent
            token_rect = QRectF(measured.rect)
            token_rect.moveTopLeft(self._pointf(x, top))
            text_rect = QRectF(measured.text_rect)
            text_rect.moveTopLeft(
                self._pointf(
                    x + measured.text_rect.x(),
                    baseline - measured.ascent,
                )
            )
            placed.append(
                _PaintToken(
                    token=measured.token,
                    rect=token_rect,
                    font=measured.font,
                    text_rect=text_rect,
                )
            )
        return tuple(placed)

    def _measure_token(self, token: _InlineToken) -> _MeasuredToken:
        """Return one measured token with baseline-aware geometry metadata."""

        font = self._font_for_token(token)
        metrics = QFontMetricsF(font)
        rect, text_rect = _measure_token_geometry(token, font)
        if token.kind == "chip":
            top_padding = _CHIP_PADDING_Y
            bottom_padding = _CHIP_PADDING_Y
        elif token.kind == "code":
            top_padding = _CODE_PADDING_Y
            bottom_padding = _CODE_PADDING_Y
        else:
            top_padding = _TEXT_LINE_PADDING_Y
            bottom_padding = _TEXT_LINE_PADDING_Y
        return _MeasuredToken(
            token=token,
            font=font,
            rect=rect,
            text_rect=text_rect,
            ascent=metrics.ascent(),
            descent=metrics.descent(),
            top_padding=top_padding,
            bottom_padding=bottom_padding,
        )

    def _font_for_token(self, token: _InlineToken) -> QFont:
        """Return the font used to paint one inline token."""

        font = QFont(self.font())
        font.setPointSizeF(
            _CAPTION_FONT_POINT_SIZE if self._compact else _BASE_FONT_POINT_SIZE
        )
        font.setBold(token.style.bold)
        font.setItalic(token.style.italic)
        font.setUnderline(token.style.underline and not token.style.code)
        font.setStrikeOut(token.style.strikethrough and not token.style.code)
        if token.style.code:
            font.setFamily("Cascadia Mono")
        return font

    def _target_at_position(self, position) -> str | None:  # type: ignore[no-untyped-def]
        """Return the interactive target under one pointer position when any."""

        token = self._paint_token_at_position(position)
        if token is None:
            return None
        return token.token.style.link_target

    def _paint_token_at_position(
        self,
        position: QPoint | QPointF,
    ) -> _PaintToken | None:
        """Return the painted token under one pointer position when any."""

        for token in self._layout_for_width(self.width())[0]:
            if token.rect.contains(position):
                return token
        return None

    def _chip_token_at_position(
        self,
        position: QPoint | QPointF,
    ) -> _PaintToken | None:
        """Return the tag-chip token under one pointer position when any."""

        token = self._paint_token_at_position(position)
        if token is None or token.token.kind != "chip":
            return None
        if _chip_target_tag(token.token.style.link_target) is None:
            return None
        return token

    def _show_chip_context_menu(
        self,
        *,
        chip_token: _PaintToken,
        event: QContextMenuEvent,
    ) -> None:
        """Build and show the chip-local context menu for one right-click."""

        target_tag = _chip_target_tag(chip_token.token.style.link_target)
        if target_tag is None:
            event.ignore()
            return
        entries = [
            MenuItem(
                "danbooru_chip.copy_tag",
                _COPY_TAG_ACTION_TEXT,
                callback=self._copy_tag_callback(target_tag),
            )
        ]
        if self._open_url is not None:
            entries.append(
                MenuItem(
                    "danbooru_chip.open_browser",
                    _OPEN_IN_BROWSER_ACTION_TEXT,
                    callback=self._open_tag_callback(target_tag),
                )
            )
        menu = QFluentMenuRenderer(parent=self).render(
            MenuModel(entries=tuple(entries))
        )
        menu.exec(event.globalPos())
        event.accept()

    def _copy_tag_to_clipboard(self, tag_name: str) -> None:
        """Copy one Danbooru tag target using the app's display formatter."""

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(prompt_display_text_from_tag(tag_name))

    def _copy_tag_callback(self, tag_name: str) -> Callable[[], None]:
        """Return a callback that copies one chip tag."""

        return lambda: self._copy_tag_to_clipboard(tag_name)

    def _open_tag_in_browser(self, tag_name: str) -> None:
        """Open one Danbooru tag chip target in the user's browser."""

        if self._open_url is None:
            return
        self._open_url(f"{_DANBOORU_WIKI_PAGE_BASE_URL}{quote(tag_name)}")

    def _open_tag_callback(self, tag_name: str) -> Callable[[], None]:
        """Return a callback that opens one chip tag in the browser."""

        return lambda: self._open_tag_in_browser(tag_name)

    @staticmethod
    def _pointf(x: float, y: float) -> QPointF:
        """Return one lazily constructed point value for layout translation."""

        return QPointF(x, y)


def _chip_target_tag(link_target: str | None) -> str | None:
    """Return the raw Danbooru tag target carried by one chip link target."""

    if link_target is None or not link_target.startswith(_WIKI_SCHEME_PREFIX):
        return None
    return unquote(link_target.split(":", 1)[1])


def _tokens_from_nodes(
    nodes: tuple[DanbooruWikiInlineNode, ...],
    *,
    inherited_style: _InlineStyle | None = None,
) -> tuple[_InlineToken, ...]:
    """Flatten semantic inline nodes into paintable layout tokens."""

    style = _InlineStyle() if inherited_style is None else inherited_style
    tokens: list[_InlineToken] = []
    for node in nodes:
        if isinstance(node, DanbooruWikiTextNode):
            tokens.extend(_split_text_tokens(node.text, style=style))
            continue
        if isinstance(node, DanbooruWikiExternalLinkNode):
            tokens.extend(
                _split_text_tokens(
                    node.label,
                    style=_replace_style(
                        style,
                        link_target=node.href,
                        replace_link_target=True,
                    ),
                )
            )
            continue
        if isinstance(node, DanbooruWikiWikiLinkNode):
            tokens.extend(
                _split_text_tokens(
                    node.display_label,
                    style=_replace_style(
                        style,
                        link_target=f"{_WIKI_SCHEME_PREFIX}{quote(node.target_title)}",
                        replace_link_target=True,
                    ),
                )
            )
            continue
        if isinstance(node, DanbooruWikiSearchLinkNode):
            tokens.extend(
                _split_text_tokens(
                    node.query_text,
                    style=_replace_style(
                        style,
                        link_target=node.href,
                        replace_link_target=True,
                    ),
                )
            )
            continue
        if isinstance(node, DanbooruWikiCodeNode):
            tokens.append(
                _InlineToken(
                    kind="code",
                    text=node.text,
                    style=_replace_style(style, code=True),
                )
            )
            continue
        if isinstance(node, DanbooruWikiLineBreakNode):
            tokens.append(
                _InlineToken(
                    kind="linebreak",
                    text="",
                    style=style,
                )
            )
            continue
        if isinstance(node, DanbooruWikiTagChipNode):
            tokens.append(
                _InlineToken(
                    kind="chip",
                    text=node.display_label,
                    style=_replace_style(
                        style,
                        link_target=f"{_WIKI_SCHEME_PREFIX}{quote(node.tag_name)}",
                        replace_link_target=True,
                    ),
                    category_name=node.category_name,
                )
            )
            continue
        child_style = _replace_style(
            style,
            bold=style.bold or node.bold,
            italic=style.italic or node.italic,
            underline=style.underline or node.underline,
            strikethrough=style.strikethrough or node.strikethrough,
        )
        tokens.extend(_tokens_from_nodes(node.children, inherited_style=child_style))
    return tuple(tokens)


def _split_text_tokens(text: str, *, style: _InlineStyle) -> list[_InlineToken]:
    """Split one text run into layout tokens while preserving spaces."""

    tokens: list[_InlineToken] = []
    for piece in _TOKEN_SPLIT_PATTERN.findall(text):
        tokens.append(
            _InlineToken(
                kind="space" if piece.isspace() else "text",
                text=piece,
                style=style,
            )
        )
    return tokens


def _replace_style(
    style: _InlineStyle,
    *,
    bold: bool | None = None,
    italic: bool | None = None,
    underline: bool | None = None,
    strikethrough: bool | None = None,
    link_target: str | None = None,
    replace_link_target: bool = False,
    code: bool | None = None,
) -> _InlineStyle:
    """Return one updated immutable style snapshot."""

    return _InlineStyle(
        bold=style.bold if bold is None else bold,
        italic=style.italic if italic is None else italic,
        underline=style.underline if underline is None else underline,
        strikethrough=(style.strikethrough if strikethrough is None else strikethrough),
        link_target=style.link_target if not replace_link_target else link_target,
        code=style.code if code is None else code,
    )


def _measure_token_geometry(
    token: _InlineToken,
    font: QFont,
) -> tuple[QRectF, QRectF]:
    """Return one paint rect and inner text rect for an inline token."""

    metrics = QFontMetricsF(font)
    text_width = max(0.0, metrics.horizontalAdvance(token.text))
    text_height = max(1.0, metrics.height())
    if token.kind == "chip":
        rect = QRectF(
            0.0,
            0.0,
            text_width + (_CHIP_PADDING_X * 2.0),
            text_height + (_CHIP_PADDING_Y * 2.0),
        )
        text_rect = rect.adjusted(
            _CHIP_PADDING_X, _CHIP_PADDING_Y, -_CHIP_PADDING_X, -_CHIP_PADDING_Y
        )
        return rect, text_rect
    if token.kind == "code":
        rect = QRectF(
            0.0,
            0.0,
            text_width + (_CODE_PADDING_X * 2.0),
            text_height + (_CODE_PADDING_Y * 2.0),
        )
        text_rect = rect.adjusted(
            _CODE_PADDING_X, _CODE_PADDING_Y, -_CODE_PADDING_X, -_CODE_PADDING_Y
        )
        return rect, text_rect
    rect = QRectF(0.0, 0.0, text_width, text_height)
    return rect, QRectF(rect)


def _is_dark_palette(widget: QWidget) -> bool:
    """Return whether the widget palette background reads as dark."""

    color = widget.palette().window().color()
    return color.lightnessF() < 0.5


def _line_height(line_tokens: list[tuple[_MeasuredToken, float]]) -> float:
    """Return the total placed height for one measured line."""

    if not line_tokens:
        return 0.0
    return max(measured.baseline_ascent for measured, _ in line_tokens) + max(
        measured.baseline_descent for measured, _ in line_tokens
    )


def _aligned_stroke_rect(rect: QRectF) -> QRectF:
    """Return one crisp pixel-aligned stroke rect for rounded outlines."""

    x = round(rect.x()) + 0.5
    y = round(rect.y()) + 0.5
    width = max(1.0, round(rect.width()) - 1.0)
    height = max(1.0, round(rect.height()) - 1.0)
    return QRectF(x, y, width, height)


def _stroke_pen(color: QColor) -> QPen:
    """Return the pen used for crisp one-pixel rounded outlines."""

    pen = QPen(color)
    pen.setWidthF(1.0)
    return pen


__all__ = ["DanbooruWikiInlineFlow"]
