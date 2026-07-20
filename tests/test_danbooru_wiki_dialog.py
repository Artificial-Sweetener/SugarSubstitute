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

"""Widget tests for the native Danbooru wiki dialog."""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QTranslator, Qt, QUrl
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QWidget
from qfluentwidgets import TitleLabel, ToolButton  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.tool_tip import (  # type: ignore[import-untyped]
    ToolTipFilter,
)

from substitute.application.danbooru import (
    DanbooruContentFreshnessState,
    DanbooruFailureReason,
    DanbooruImagePreviewState,
    DanbooruWikiBlock,
    DanbooruWikiImageReference,
    DanbooruWikiImageReferenceBlock,
    DanbooruWikiInlineNode,
    DanbooruWikiListBlock,
    DanbooruWikiParagraphBlock,
    DanbooruWikiQuoteBlock,
    DanbooruWikiTagChipNode,
    DanbooruWikiContentLookupResult,
    DanbooruWikiNavigationEntry,
    DanbooruWikiContentPage,
    DanbooruWikiImagePreview,
    DanbooruWikiSectionContent,
    DanbooruWikiListItem,
    DanbooruWikiWikiLinkNode,
)
from tests.execution_testing import QueuedTaskSubmitter
from substitute.presentation.danbooru import (
    DanbooruWikiImageCard,
    DanbooruWikiInlineFlow,
)
from substitute.presentation.dialogs import (
    danbooru_wiki_dialog as danbooru_wiki_dialog_module,
)
from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    DanbooruWikiDialog,
    QtDanbooruWikiLookupDispatcher,
    _DialogLoadResult,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real Danbooru wiki dialog tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _StubDanbooruWikiService:
    """Provide deterministic lookup results for the wiki dialog."""

    def __init__(
        self,
        *,
        selection_results: dict[str, DanbooruWikiContentLookupResult],
        title_results: dict[str, DanbooruWikiContentLookupResult] | None = None,
        section_resolver: Callable[
            [tuple[DanbooruWikiSectionContent, ...]],
            tuple[DanbooruWikiSectionContent, ...],
        ]
        | None = None,
    ) -> None:
        """Store deterministic lookup results and capture navigation calls."""

        self._selection_results = dict(selection_results)
        self._title_results = dict(title_results or {})
        self._section_resolver = section_resolver
        self.calls: list[tuple[str, str]] = []

    def lookup_selection(self, selection_text: str) -> DanbooruWikiContentLookupResult:
        """Return the configured selection-based lookup result."""

        self.calls.append(("selection", selection_text))
        return self._selection_results[selection_text]

    def lookup_title(self, title: str) -> DanbooruWikiContentLookupResult:
        """Return the configured title-based lookup result."""

        self.calls.append(("title", title))
        return self._title_results[title]

    def resolve_sections(
        self,
        sections: tuple[DanbooruWikiSectionContent, ...],
    ) -> tuple[DanbooruWikiSectionContent, ...]:
        """Return parsed sections unchanged for deterministic dialog tests."""

        if self._section_resolver is None:
            return sections
        return self._section_resolver(sections)


class _ImmediateDispatcher:
    """Run dialog lookups immediately for deterministic widget tests."""

    def submit(
        self,
        lookup: Callable[[], _DialogLoadResult],
        *,
        completed: Callable[[_DialogLoadResult], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Execute the lookup inline and report through the callbacks."""

        try:
            completed(lookup())
        except BaseException as error:  # noqa: BLE001
            failed(error)


class _StubImagePreviewResolver:
    """Return deterministic image preview outcomes for parsed post embeds."""

    def __init__(
        self,
        previews_by_reference: dict[tuple[str, int], DanbooruWikiImagePreview],
    ) -> None:
        """Store preview results keyed by Danbooru embed kind and identifier."""

        self._previews_by_reference = dict(previews_by_reference)

    def resolve_preview_for_reference(
        self,
        *,
        source_kind: str,
        source_id: int,
    ) -> DanbooruWikiImagePreview:
        """Return the configured preview for the requested Danbooru embed."""

        return self._previews_by_reference[(source_kind, source_id)]


class _StubRecentPostsResolver:
    """Return deterministic recent visible post ids for wiki dialog tests."""

    def __init__(self, post_ids_by_tag: dict[str, tuple[int, ...]]) -> None:
        """Store deterministic recent post ids keyed by Danbooru tag title."""

        self._post_ids_by_tag = dict(post_ids_by_tag)

    def list_recent_visible_post_ids(
        self,
        tag_name: str,
        *,
        desired_count: int = 5,
    ) -> tuple[int, ...]:
        """Return the configured recent visible posts for the supplied tag."""

        return self._post_ids_by_tag.get(tag_name, ())[:desired_count]


def test_qt_danbooru_wiki_lookup_dispatcher_cancels_pending_lookup_on_shutdown() -> (
    None
):
    """Lookup dispatcher shutdown should cancel dialog-scoped execution work."""

    _app()
    parent = QWidget()
    submitter = QueuedTaskSubmitter()
    close_calls: list[str] = []
    dispatcher = QtDanbooruWikiLookupDispatcher(
        parent,
        submitter=submitter,
        close_submitter=lambda: close_calls.append("closed"),
    )

    dispatcher.submit(
        lambda: cast(_DialogLoadResult, object()),
        completed=lambda _result: None,
        failed=lambda _error: None,
    )
    assert len(submitter.handles) == 1
    assert submitter.cancellations[0].is_cancelled is False

    dispatcher._shutdown()  # noqa: SLF001

    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == "danbooru_wiki_dialog_lookup_shutdown"
    assert submitter.handles[0].cancel_reason == "danbooru_wiki_dialog_lookup_shutdown"
    assert close_calls == ["closed"]


def test_danbooru_wiki_dialog_renders_metadata_and_body() -> None:
    """Dialog should render the wiki page metadata and browser content."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert dialog._title_label.text() == '"long hair"'
    assert dialog._post_count_label.text() == "5,786 posts"
    assert dialog._pixiv_prefix_label.text() == "On Pixiv:"
    assert (
        '<a href="https://www.pixiv.net/en/tags/long%20locks/artworks">long locks</a>, '
        '<a href="https://www.pixiv.net/en/tags/flowing%20hair/artworks">flowing hair</a>'
        == dialog._pixiv_label.text()
    )
    assert _dialog_contains_text(dialog, "Hair that extends below the shoulders.")
    assert dialog._open_button.isEnabled() is True
    assert dialog._copy_button.isEnabled() is True


def test_danbooru_header_actions_retranslate_without_recreating_dialog() -> None:
    """Keep persistent header tooltips and accessibility in the active locale."""

    app = _app()
    resource_root = (
        Path(__file__).resolve().parents[1]
        / "substitute"
        / "presentation"
        / "resources"
        / "i18n"
    )
    chinese = QTranslator()
    japanese = QTranslator()
    assert chinese.load(str(resource_root / "sugarsubstitute_zh_CN.qm"))
    assert japanese.load(str(resource_root / "sugarsubstitute_ja_JP.qm"))
    assert app.installTranslator(chinese)
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    buttons = (
        dialog._back_button,
        dialog._forward_button,
        dialog._copy_button,
        dialog._open_button,
        dialog._close_button,
    )
    try:
        assert [button.toolTip() for button in buttons] == [
            "返回",
            "前进",
            "复制标签标题",
            "在浏览器中打开标签百科文章",
            "关闭",
        ]
        assert [button.accessibleName() for button in buttons] == [
            button.toolTip() for button in buttons
        ]

        assert app.removeTranslator(chinese)
        assert app.installTranslator(japanese)
        for button in buttons:
            app.sendEvent(button, QEvent(QEvent.Type.LanguageChange))

        assert [button.toolTip() for button in buttons] == [
            "戻る",
            "進む",
            "タグのタイトルをコピー",
            "タグの Wiki 記事をブラウザーで開く",
            "閉じる",
        ]
        assert [button.accessibleName() for button in buttons] == [
            button.toolTip() for button in buttons
        ]
    finally:
        app.removeTranslator(japanese)
        app.removeTranslator(chinese)
        dialog.close()


def test_danbooru_wiki_dialog_routes_internal_links_inside_modal() -> None:
    """Internal wiki links should navigate to the next page inside the dialog."""

    app = _app()
    service = _StubDanbooruWikiService(
        selection_results={"long hair": _success_result(_page_view())},
        title_results={
            "short_hair": _success_result(
                _page_view(
                    title="short_hair",
                    display_title="short hair",
                    body_dtext="h4. Definition\n\nHair above the shoulders.",
                )
            )
        },
    )
    dialog = DanbooruWikiDialog(
        wiki_service=service,
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    dialog._handle_anchor_clicked(QUrl("danbooru-wiki:short_hair"))
    app.processEvents()

    assert dialog._title_label.text() == '"short hair"'
    assert _dialog_contains_text(dialog, "Hair above the shoulders.")
    assert dialog._back_button.isEnabled() is True
    assert service.calls == [("selection", "long hair"), ("title", "short_hair")]


def test_danbooru_wiki_dialog_renders_valid_tags_as_native_chip_flows() -> None:
    """Resolved valid tags should render through the native inline-flow chip path."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "long hair": _success_result(
                    _page_view(body_dtext="h4. See also\n\n* [[short_hair]]")
                )
            },
            section_resolver=lambda sections: _chipify_target(
                sections,
                target_title="short_hair",
                display_label="short hair",
                category_name="general",
            ),
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    inline_flow = _first_inline_flow_with_text(dialog, "short hair")
    assert "danbooru-wiki:short_hair" in inline_flow.link_targets()


def test_danbooru_wiki_dialog_routes_chip_clicks_inside_modal() -> None:
    """Resolved tag chips should navigate inside the dialog when clicked."""

    app = _app()
    service = _StubDanbooruWikiService(
        selection_results={
            "long hair": _success_result(
                _page_view(body_dtext="h4. See also\n\n* [[short_hair]]")
            )
        },
        title_results={
            "short_hair": _success_result(
                _page_view(
                    title="short_hair",
                    display_title="short hair",
                    body_dtext="h4. Definition\n\nHair above the shoulders.",
                )
            )
        },
        section_resolver=lambda sections: _chipify_target(
            sections,
            target_title="short_hair",
            display_label="short hair",
            category_name="general",
        ),
    )
    dialog = DanbooruWikiDialog(
        wiki_service=service,
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    inline_flow = _first_inline_flow_with_text(dialog, "short hair")
    inline_flow.linkActivated.emit("danbooru-wiki:short_hair")
    app.processEvents()

    assert dialog._title_label.text() == '"short hair"'
    assert _dialog_contains_text(dialog, "Hair above the shoulders.")


def test_danbooru_wiki_dialog_keeps_mixed_prose_on_rich_text_path() -> None:
    """Mixed prose plus chips should render through the native inline-flow path."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "serious": _success_result(
                    _page_view(title="serious", display_title="serious")
                )
            },
            section_resolver=lambda sections: _chipify_target(
                sections,
                target_title="short_hair",
                display_label="short hair",
                category_name="general",
            ),
        ),
        selection_text="serious",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert any(
        "See short hair." in view.plain_text()
        for view in dialog.findChildren(DanbooruWikiInlineFlow)
    )
    assert not any(
        'href="danbooru-wiki:short_hair" style="background-color:' in label.text()
        for label in dialog.findChildren(QLabel)
    )


def test_danbooru_wiki_dialog_uses_icon_only_header_actions() -> None:
    """The dialog header should use the house modal action widgets and title class."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert dialog._back_button.text() == ""
    assert dialog._forward_button.text() == ""
    assert dialog._copy_button.text() == ""
    assert dialog._open_button.text() == ""
    assert dialog._close_button.text() == ""
    assert type(dialog._back_button) is ToolButton
    assert type(dialog._forward_button) is ToolButton
    assert type(dialog._copy_button) is ToolButton
    assert type(dialog._open_button) is ToolButton
    assert type(dialog._close_button) is ToolButton
    assert isinstance(dialog._title_label, TitleLabel)
    assert dialog._title_label.text() == '"long hair"'
    assert dialog._back_button.toolTip() == "Back"
    assert dialog._forward_button.toolTip() == "Forward"
    assert dialog._copy_button.toolTip() == "Copy tag title"
    assert dialog._open_button.toolTip() == "Open tag wiki article in browser"
    assert dialog._close_button.toolTip() == "Close"
    assert dialog._back_button.findChildren(ToolTipFilter)
    assert dialog._forward_button.findChildren(ToolTipFilter)
    assert dialog._copy_button.findChildren(ToolTipFilter)
    assert dialog._open_button.findChildren(ToolTipFilter)
    assert dialog._close_button.findChildren(ToolTipFilter)


def test_danbooru_wiki_dialog_header_has_no_divider_frame() -> None:
    """The header should no longer add a separator line under the title rows."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert not any(
        frame.frameShape() == QFrame.Shape.HLine
        for frame in dialog._header.findChildren(QFrame)
    )


def test_danbooru_wiki_dialog_hides_footer_button_group() -> None:
    """The old footer chin should no longer be visible or reserve height."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert dialog.buttonGroup.isHidden() is True
    assert dialog.buttonGroup.height() == 0


def test_danbooru_wiki_dialog_uses_split_surface_shell_styling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wiki modal should split styling between header and body surfaces."""

    app = _app()
    monkeypatch.setattr(danbooru_wiki_dialog_module, "_is_dark_theme", lambda: True)
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    stylesheet = dialog.widget.styleSheet()
    assert "QWidget#DanbooruWikiDialogHeader {" in stylesheet
    assert "background: #2b2b2b;" in stylesheet
    assert "QWidget#DanbooruWikiDialogSurface {" in stylesheet
    assert "QWidget#DanbooruWikiDialogBody {" in stylesheet
    assert "background: #202020;" in stylesheet
    assert "rgba(32, 32, 32, 0.94)" not in stylesheet
    assert "rgba(251, 251, 251, 0.97)" not in stylesheet
    assert "rgba(244, 244, 244, 0.98)" not in stylesheet


def test_danbooru_wiki_dialog_header_copy_uses_unquoted_title() -> None:
    """The header copy action should copy the plain title, not the quoted label."""

    app = _app()
    clipboard = QGuiApplication.clipboard()
    clipboard.clear()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    dialog._copy_button.click()

    assert clipboard.text() == "long hair"


def test_danbooru_wiki_dialog_close_button_rejects_dialog() -> None:
    """The header close action should reject the modal."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    dialog._close_button.click()
    app.processEvents()

    assert dialog.result() == DanbooruWikiDialog.DialogCode.Rejected


def test_danbooru_wiki_dialog_routes_external_links_to_browser() -> None:
    """External links should delegate to the supplied URL opener."""

    app = _app()
    opened_urls: list[str] = []
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        open_url=lambda url: _record_opened_url(opened_urls, url),
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    dialog._handle_anchor_clicked(QUrl("https://example.com/wiki"))

    assert opened_urls == ["https://example.com/wiki"]


def test_danbooru_wiki_dialog_sizes_responsively_from_top_level_parent_window() -> None:
    """The modal shell should size from the owning top-level window, not a child."""

    app = _app()
    parent_window = QWidget()
    parent_window.resize(1000, 800)
    parent_window.move(120, 80)
    parent_child = QWidget(parent_window)
    parent_window.show()
    app.processEvents()

    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
        parent=parent_child,
    )
    dialog.show()
    app.processEvents()

    assert dialog.widget.width() == 850
    assert dialog.widget.height() == 680
    assert (
        abs(
            _widget_global_center(dialog.widget).x()
            - parent_window.frameGeometry().center().x()
        )
        <= 1
    )
    assert (
        abs(
            _widget_global_center(dialog.widget).y()
            - parent_window.frameGeometry().center().y()
        )
        <= 1
    )


def test_danbooru_wiki_dialog_clamps_responsive_size_to_minimums() -> None:
    """Very small parent windows should still produce a usable modal shell."""

    app = _app()
    parent_window = QWidget()
    parent_window.resize(600, 400)
    parent_window.show()
    app.processEvents()

    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
        parent=parent_window,
    )
    dialog.show()
    app.processEvents()

    assert dialog.widget.width() == 840
    assert dialog.widget.height() == 560


def test_danbooru_wiki_dialog_resizes_with_parent_while_open() -> None:
    """The modal shell should stay proportionate when the parent window resizes."""

    app = _app()
    parent_window = QWidget()
    parent_window.resize(1000, 800)
    parent_window.move(220, 140)
    parent_window.show()
    app.processEvents()

    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={"long hair": _success_result(_page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
        parent=parent_window,
    )
    dialog.show()
    app.processEvents()

    parent_window.resize(1400, 1000)
    app.processEvents()

    assert dialog.widget.width() == 1190
    assert dialog.widget.height() == 850
    assert (
        abs(
            _widget_global_center(dialog.widget).x()
            - parent_window.frameGeometry().center().x()
        )
        <= 1
    )
    assert (
        abs(
            _widget_global_center(dialog.widget).y()
            - parent_window.frameGeometry().center().y()
        )
        <= 1
    )


def test_danbooru_wiki_dialog_routes_pixiv_alias_links_to_browser() -> None:
    """Pixiv aliases in the metadata row should open through the supplied URL opener."""

    app = _app()
    opened_urls: list[str] = []
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "artist name": _success_result(
                    _page_view(
                        title="artist_name",
                        display_title="artist name",
                        body_dtext="h4. Definition\n\nArtist page.",
                        other_names=("pixiv #12345678",),
                    )
                )
            }
        ),
        selection_text="artist name",
        open_url=lambda url: _record_opened_url(opened_urls, url),
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert dialog._pixiv_prefix_label.text() == "On Pixiv:"
    assert (
        '<a href="https://www.pixiv.net/artworks/12345678">pixiv #12345678</a>'
        == dialog._pixiv_label.text()
    )
    dialog._pixiv_label.linkActivated.emit("https://www.pixiv.net/artworks/12345678")

    assert opened_urls == ["https://www.pixiv.net/artworks/12345678"]


def test_danbooru_wiki_dialog_routes_plain_other_names_to_pixiv_tag_search() -> None:
    """Wiki other-names entries should render as Pixiv tag-search links."""

    app = _app()
    opened_urls: list[str] = []
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "contrapposto": _success_result(
                    _page_view(
                        title="contrapposto",
                        display_title="contrapposto",
                        body_dtext="h4. Definition\n\nBody pose.",
                        other_names=("コントラポスト", "透視絶壁"),
                    )
                )
            }
        ),
        selection_text="contrapposto",
        open_url=lambda url: _record_opened_url(opened_urls, url),
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert dialog._pixiv_prefix_label.text() == "On Pixiv:"
    assert (
        '<a href="https://www.pixiv.net/en/tags/%E3%82%B3%E3%83%B3%E3%83%88%E3%83%A9%E3%83%9D%E3%82%B9%E3%83%88/artworks">コントラポスト</a>, '
        '<a href="https://www.pixiv.net/en/tags/%E9%80%8F%E8%A6%96%E7%B5%B6%E5%A3%81/artworks">透視絶壁</a>'
        == dialog._pixiv_label.text()
    )

    dialog._pixiv_label.linkActivated.emit(
        "https://www.pixiv.net/en/tags/%E3%82%B3%E3%83%B3%E3%83%88%E3%83%A9%E3%83%9D%E3%82%B9%E3%83%88/artworks"
    )

    assert opened_urls == [
        "https://www.pixiv.net/en/tags/%E3%82%B3%E3%83%B3%E3%83%88%E3%83%A9%E3%83%9D%E3%82%B9%E3%83%88/artworks"
    ]


def test_danbooru_wiki_dialog_aligns_pixiv_row_to_post_count_baseline() -> None:
    """Pixiv metadata should share the same text baseline as the post-count label."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "ribbon": _success_result(
                    _page_view(
                        title="ribbon",
                        display_title="ribbon",
                        body_dtext="h4. Definition\n\nRibbon page.",
                        other_names=("リボン", "띠본", "丝带"),
                    )
                )
            }
        ),
        selection_text="ribbon",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    post_baseline = (
        dialog._post_count_label.y() + dialog._post_count_label.fontMetrics().ascent()
    )
    pixiv_baseline = (
        dialog._pixiv_prefix_label.y()
        + dialog._pixiv_prefix_label.fontMetrics().ascent()
    )

    assert abs(post_baseline - pixiv_baseline) <= 1


def test_danbooru_wiki_dialog_routes_pool_links_to_browser_with_absolute_url() -> None:
    """Quoted relative Danbooru links should resolve and open externally."""

    app = _app()
    opened_urls: list[str] = []
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "serious": _success_result(
                    _page_view(
                        title="serious",
                        display_title="serious",
                        body_dtext='h4. See also\n\n"Pool: Serious Beauty":/pools/4339',
                    )
                )
            }
        ),
        selection_text="serious",
        open_url=lambda url: _record_opened_url(opened_urls, url),
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    pool_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if 'href="https://danbooru.donmai.us/pools/4339"' in label.text()
    )
    pool_label.linkActivated.emit("https://danbooru.donmai.us/pools/4339")

    assert opened_urls == ["https://danbooru.donmai.us/pools/4339"]


def test_danbooru_wiki_dialog_renders_double_brace_search_tags_as_links() -> None:
    """Danbooru double-brace tokens should render as clickable post-search links."""

    app = _app()
    opened_urls: list[str] = []
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "lowres": _success_result(
                    _page_view(
                        title="lowres",
                        display_title="lowres",
                        body_dtext=(
                            "An image less than 500 pixels wide or tall. "
                            "Approximately equivalent to {{mpixels:<=0.25}}."
                        ),
                    )
                )
            }
        ),
        selection_text="lowres",
        open_url=lambda url: _record_opened_url(opened_urls, url),
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    search_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if 'href="https://danbooru.donmai.us/posts?tags=mpixels%3A%3C%3D0.25"'
        in label.text()
    )
    assert "{{mpixels:<=0.25}}" not in search_label.text()
    search_label.linkActivated.emit(
        "https://danbooru.donmai.us/posts?tags=mpixels%3A%3C%3D0.25"
    )

    assert opened_urls == ["https://danbooru.donmai.us/posts?tags=mpixels%3A%3C%3D0.25"]


def test_danbooru_wiki_dialog_uses_compact_list_indentation() -> None:
    """List blocks should use the tighter native indent, not the older wide offset."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "hair styles": _success_result(
                    _page_view(
                        title="hair_styles",
                        display_title="hair styles",
                        body_dtext=(
                            "h4. See also\n\n"
                            "* [[bangs]]\n"
                            "* [[slicked_back_hair|hair slicked back]]"
                        ),
                    )
                )
            }
        ),
        selection_text="hair styles",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    list_label = next(
        label for label in dialog.findChildren(QLabel) if "<ul>" in label.text()
    )
    assert "ul,ol { margin: 0 0 10px 0; padding-left: 14px; }" in list_label.text()


def test_danbooru_wiki_dialog_shows_not_found_state() -> None:
    """Missing wiki pages should show a native not-found body state."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "missing tag": DanbooruWikiContentLookupResult(
                    page=None,
                    navigation_entry=None,
                    requested_text="missing tag",
                    resolved_title="missing_tag",
                    failure_reason=DanbooruFailureReason.NOT_FOUND,
                )
            }
        ),
        selection_text="missing tag",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert dialog._status_title_label.text() == "Definition not found"
    assert dialog._title_label.text() == '"missing tag"'
    assert 'No Danbooru wiki page was found for "missing tag".' == (
        dialog._status_body_label.text()
    )


def test_danbooru_wiki_dialog_renders_hidden_image_placeholders() -> None:
    """Policy-hidden images should render native placeholder copy in the dialog."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "long hair": _success_result(
                    _page_view(
                        body_dtext="h4. Examples\n\n!post #12345",
                    )
                )
            }
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", 12345): DanbooruWikiImagePreview(
                    post_id=12345,
                    canonical_post_url="https://danbooru.donmai.us/posts/12345",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating="e",
                    width=None,
                    height=None,
                    hidden_reason="Hidden by Danbooru content settings.",
                )
            }
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert _dialog_contains_text(dialog, "Hidden by content preferences")
    assert len(dialog.findChildren(DanbooruWikiImageCard)) == 1


def test_danbooru_wiki_dialog_renders_expand_toc_without_raw_dtext_leaks() -> None:
    """Expand wrappers and fragment links should not leak raw DText into the dialog."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "tag group:sleeves": _success_result(
                    _page_view(
                        title="tag_group:sleeves",
                        display_title="tag group:sleeves",
                        body_dtext=(
                            "[See [[tag groups]].]\n\n"
                            "[expand=Table of Contents]\n"
                            '* 1. "Colors":#dtext-colors\n'
                            "[/expand]\n\n"
                            "h4#colors. Colors\n"
                            "* [[Black sleeves]]\n"
                        ),
                    )
                )
            }
        ),
        selection_text="tag group:sleeves",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert any(
        "See " in text and "tag groups" in text for text in _dialog_texts(dialog)
    )
    assert not _dialog_contains_text(dialog, "[expand=Table of Contents]")
    assert not _dialog_contains_text(dialog, '"Colors":#dtext-colors')
    assert any(
        'href="danbooru-fragment:dtext-colors"' in label.text()
        for label in dialog.findChildren(QLabel)
    )


def test_danbooru_wiki_dialog_routes_fragment_links_inside_modal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quoted fragment links should route to the content-view anchor handler."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "tag group:sleeves": _success_result(
                    _page_view(
                        title="tag_group:sleeves",
                        display_title="tag group:sleeves",
                        body_dtext=(
                            "[expand=Table of Contents]\n"
                            '* 1. "Colors":#dtext-colors\n'
                            "[/expand]\n\n"
                            "h4#padding. Padding\n"
                            + "\n".join("* [[Black sleeves]]" for _ in range(25))
                            + "\n\nh4#colors. Colors\n* [[White sleeves]]\n"
                        ),
                    )
                )
            }
        ),
        selection_text="tag group:sleeves",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    scrolled_to: list[str] = []
    monkeypatch.setattr(
        dialog._content_view,
        "scroll_to_anchor",
        lambda anchor_id: scrolled_to.append(anchor_id),
    )
    dialog._handle_anchor_clicked(QUrl("danbooru-fragment:dtext-colors"))
    app.processEvents()

    assert scrolled_to == ["dtext-colors"]


def test_danbooru_wiki_image_card_preserves_visible_preview_aspect_ratio(
    tmp_path: Path,
) -> None:
    """Ready preview cards should be bounded by height, not by a square box."""

    app = _app()
    image_path = tmp_path / "wide_preview.png"
    _write_image(image_path, width=320, height=160)
    card = DanbooruWikiImageCard(
        preview=DanbooruWikiImagePreview(
            post_id=12345,
            canonical_post_url="https://danbooru.donmai.us/posts/12345",
            state=DanbooruImagePreviewState.READY,
            local_path=image_path,
            rating="g",
            width=320,
            height=160,
        ),
        open_url=lambda _url: True,
    )
    card.show()
    app.processEvents()

    assert card.width() == 312
    assert card.height() == 156


def test_danbooru_wiki_image_card_keeps_hidden_placeholder_square() -> None:
    """Hidden preview cards should still use the square placeholder footprint."""

    app = _app()
    card = DanbooruWikiImageCard(
        preview=DanbooruWikiImagePreview(
            post_id=12345,
            canonical_post_url="https://danbooru.donmai.us/posts/12345",
            state=DanbooruImagePreviewState.HIDDEN,
            local_path=None,
            rating="q",
            width=320,
            height=160,
            hidden_reason="Hidden by Danbooru content settings.",
        ),
        open_url=lambda _url: True,
    )
    card.show()
    app.processEvents()

    assert card.width() == 156
    assert card.height() == 156


def test_danbooru_wiki_dialog_promotes_bulleted_post_embeds_to_images() -> None:
    """Bulleted Danbooru post embeds should not render as literal DText in the dialog."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "long hair": _success_result(
                    _page_view(
                        body_dtext="h4. Examples\n\n* !post #12345: [[Hime cut]]",
                    )
                )
            }
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", 12345): DanbooruWikiImagePreview(
                    post_id=12345,
                    canonical_post_url="https://danbooru.donmai.us/posts/12345",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating="q",
                    width=None,
                    height=None,
                    hidden_reason="Hidden by Danbooru content settings.",
                )
            }
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert _dialog_contains_text(dialog, "Hime cut")
    assert len(dialog.findChildren(DanbooruWikiImageCard)) == 1
    assert not any("!post" in text for text in _dialog_texts(dialog))


def test_danbooru_wiki_dialog_promotes_bulleted_asset_embeds_to_images() -> None:
    """Bulleted Danbooru asset embeds should not render as literal DText in the dialog."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "shaft look": _success_result(
                    _page_view(
                        title="shaft_look",
                        display_title="shaft look",
                        body_dtext="h4. Examples\n\n* !asset #37448022",
                    )
                )
            }
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("asset", 37448022): DanbooruWikiImagePreview(
                    post_id=37448022,
                    canonical_post_url="https://danbooru.donmai.us/media_assets/37448022",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating=None,
                    width=None,
                    height=None,
                    hidden_reason="Hidden by Danbooru content settings.",
                )
            }
        ),
        selection_text="shaft look",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert len(dialog.findChildren(DanbooruWikiImageCard)) == 1
    assert not any("!asset" in text for text in _dialog_texts(dialog))


def test_danbooru_wiki_dialog_groups_example_thumbnails_side_by_side() -> None:
    """Consecutive example embeds should render as sibling thumbnail tiles, not stacked cards."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "long hair": _success_result(
                    _page_view(
                        body_dtext=(
                            "h4. Examples\n\n"
                            "* !post #11111: [[First style]]\n"
                            "* !post #22222: [[Second style]]\n"
                        ),
                    )
                )
            }
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", 11111): DanbooruWikiImagePreview(
                    post_id=11111,
                    canonical_post_url="https://danbooru.donmai.us/posts/11111",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating="q",
                    width=None,
                    height=None,
                    hidden_reason="Hidden by Danbooru content settings.",
                ),
                ("post", 22222): DanbooruWikiImagePreview(
                    post_id=22222,
                    canonical_post_url="https://danbooru.donmai.us/posts/22222",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating="q",
                    width=None,
                    height=None,
                    hidden_reason="Hidden by Danbooru content settings.",
                ),
            }
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    image_cards = dialog.findChildren(DanbooruWikiImageCard)
    assert len(image_cards) == 2
    assert image_cards[0].y() == image_cards[1].y()


def test_danbooru_wiki_dialog_centers_thumbnails_within_gallery_cells(
    tmp_path: Path,
) -> None:
    """Visible example thumbnails and captions should stay centered in the gallery cell."""

    app = _app()
    image_path = tmp_path / "narrow_preview.png"
    _write_image(image_path, width=120, height=156)
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "bangs": _success_result(
                    _page_view(
                        title="bangs",
                        display_title="bangs",
                        body_dtext=(
                            "h4. Types of bangs\n\n"
                            "* !post #12345: [[arched bangs]] - For bangs that curve upward"
                        ),
                    )
                )
            }
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", 12345): DanbooruWikiImagePreview(
                    post_id=12345,
                    canonical_post_url="https://danbooru.donmai.us/posts/12345",
                    state=DanbooruImagePreviewState.READY,
                    local_path=image_path,
                    rating="g",
                    width=120,
                    height=156,
                )
            }
        ),
        selection_text="bangs",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    card = dialog.findChild(DanbooruWikiImageCard)
    assert card is not None
    item_layout = card.parentWidget().layout()
    assert item_layout is not None
    assert item_layout.itemAt(0).alignment() & Qt.AlignmentFlag.AlignHCenter
    assert item_layout.itemAt(1).alignment() & Qt.AlignmentFlag.AlignHCenter


def test_danbooru_wiki_dialog_indents_nested_list_items() -> None:
    """Nested DText list items should render deeper than their parent list items."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "tag group:sleeves": _success_result(
                    _page_view(
                        title="tag_group:sleeves",
                        display_title="Tag group:sleeves",
                        body_dtext=(
                            "h4#lengths. Length\n"
                            "* [[Long sleeves]]\n"
                            "** [[Sleeves past wrists]]\n"
                            "** [[Sleeves past fingers]]\n"
                            "* [[Uneven sleeves]]\n"
                        ),
                    )
                )
            },
            section_resolver=lambda sections: _chipify_target(
                _chipify_target(
                    _chipify_target(
                        _chipify_target(
                            sections,
                            target_title="Long sleeves",
                            display_label="Long sleeves",
                            category_name="general",
                        ),
                        target_title="Sleeves past wrists",
                        display_label="Sleeves past wrists",
                        category_name="general",
                    ),
                    target_title="Sleeves past fingers",
                    display_label="Sleeves past fingers",
                    category_name="general",
                ),
                target_title="Uneven sleeves",
                display_label="Uneven sleeves",
                category_name="general",
            ),
        ),
        selection_text="tag group:sleeves",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    parent_flow = _first_inline_flow_with_text(dialog, "Long sleeves")
    nested_wrist_flow = _first_inline_flow_with_text(dialog, "Sleeves past wrists")
    nested_finger_flow = _first_inline_flow_with_text(dialog, "Sleeves past fingers")
    trailing_flow = _first_inline_flow_with_text(dialog, "Uneven sleeves")

    parent_row = parent_flow.parentWidget()
    nested_wrist_row = nested_wrist_flow.parentWidget()
    nested_finger_row = nested_finger_flow.parentWidget()
    trailing_row = trailing_flow.parentWidget()
    assert parent_row is not None
    assert nested_wrist_row is not None
    assert nested_finger_row is not None
    assert trailing_row is not None
    parent_layout = parent_row.layout()
    wrist_layout = nested_wrist_row.layout()
    finger_layout = nested_finger_row.layout()
    trailing_layout = trailing_row.layout()
    assert parent_layout is not None
    assert wrist_layout is not None
    assert finger_layout is not None
    assert trailing_layout is not None

    parent_indent = parent_layout.contentsMargins().left()
    wrist_indent = wrist_layout.contentsMargins().left()
    finger_indent = finger_layout.contentsMargins().left()
    trailing_indent = trailing_layout.contentsMargins().left()

    assert wrist_indent > parent_indent
    assert finger_indent > parent_indent
    assert trailing_indent == parent_indent


def test_danbooru_wiki_dialog_routes_caption_tag_links_inside_modal() -> None:
    """Image-caption wiki links should navigate inside the dialog like body links."""

    app = _app()
    service = _StubDanbooruWikiService(
        selection_results={
            "long hair": _success_result(
                _page_view(
                    body_dtext="h4. Examples\n\n* !post #12345: [[short_hair|short]]",
                )
            )
        },
        title_results={
            "short_hair": _success_result(
                _page_view(
                    title="short_hair",
                    display_title="short hair",
                    body_dtext="h4. Definition\n\nHair above the shoulders.",
                )
            )
        },
    )
    dialog = DanbooruWikiDialog(
        wiki_service=service,
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", 12345): DanbooruWikiImagePreview(
                    post_id=12345,
                    canonical_post_url="https://danbooru.donmai.us/posts/12345",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating="q",
                    width=None,
                    height=None,
                    hidden_reason="Hidden by Danbooru content settings.",
                )
            }
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    caption_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if 'href="danbooru-wiki:short_hair"' in label.text()
    )
    caption_label.linkActivated.emit("danbooru-wiki:short_hair")
    app.processEvents()

    assert dialog._title_label.text() == '"short hair"'
    assert _dialog_contains_text(dialog, "Hair above the shoulders.")


def test_danbooru_wiki_dialog_renders_caption_tag_chips() -> None:
    """Resolved valid tag links inside captions should render through inline-flow chips."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "long hair": _success_result(
                    _page_view(
                        body_dtext="h4. Examples\n\n* !post #12345: [[short_hair|short]]",
                    )
                )
            },
            section_resolver=lambda sections: _chipify_target(
                sections,
                target_title="short_hair",
                display_label="short",
                category_name="general",
            ),
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", 12345): DanbooruWikiImagePreview(
                    post_id=12345,
                    canonical_post_url="https://danbooru.donmai.us/posts/12345",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating="q",
                    width=None,
                    height=None,
                    hidden_reason="Hidden by Danbooru content settings.",
                )
            }
        ),
        selection_text="long hair",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    inline_flow = _first_inline_flow_with_text(dialog, "short")
    assert "danbooru-wiki:short_hair" in inline_flow.link_targets()


def test_danbooru_wiki_dialog_routes_caption_external_links_to_browser() -> None:
    """Image-caption external links should open through the supplied URL opener."""

    app = _app()
    opened_urls: list[str] = []
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "contrapposto": _success_result(
                    _page_view(
                        title="contrapposto",
                        display_title="contrapposto",
                        body_dtext=(
                            "h4. Examples\n\n"
                            '* !post #12345: "Wikipedia: Contrapposto":http://en.wikipedia.org/wiki/Contrapposto'
                        ),
                    )
                )
            }
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", 12345): DanbooruWikiImagePreview(
                    post_id=12345,
                    canonical_post_url="https://danbooru.donmai.us/posts/12345",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating="q",
                    width=None,
                    height=None,
                    hidden_reason="Hidden by Danbooru content settings.",
                )
            }
        ),
        selection_text="contrapposto",
        open_url=lambda url: _record_opened_url(opened_urls, url),
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    caption_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if 'href="http://en.wikipedia.org/wiki/Contrapposto"' in label.text()
    )
    caption_label.linkActivated.emit("http://en.wikipedia.org/wiki/Contrapposto")

    assert opened_urls == ["http://en.wikipedia.org/wiki/Contrapposto"]


def test_danbooru_wiki_dialog_renders_caption_breaks_and_post_links() -> None:
    """Caption `[br]` and `post #...` text should render as breaks plus post links."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "compression artifacts": _success_result(
                    _page_view(
                        title="compression_artifacts",
                        display_title="compression artifacts",
                        body_dtext=(
                            "h4. Examples\n\n"
                            "* !post #12345: Left: No artifacts [br] Right: artifacts [br] (post #10154238)"
                        ),
                    )
                )
            }
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", 12345): DanbooruWikiImagePreview(
                    post_id=12345,
                    canonical_post_url="https://danbooru.donmai.us/posts/12345",
                    state=DanbooruImagePreviewState.HIDDEN,
                    local_path=None,
                    rating="q",
                    width=None,
                    height=None,
                    hidden_reason="Hidden by Danbooru content settings.",
                )
            }
        ),
        selection_text="compression artifacts",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    caption_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if "Left: No artifacts" in label.text()
    )
    assert "<br/>" in caption_label.text()
    assert "[br]" not in caption_label.text()
    assert 'href="https://danbooru.donmai.us/posts/10154238"' in caption_label.text()


def test_danbooru_wiki_dialog_appends_recent_posts_section_when_available() -> None:
    """Visible recent post ids should render as a bottom Posts section."""

    app = _app()
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "head tilt": _success_result(
                    _page_view(title="head_tilt", display_title="head tilt")
                )
            }
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", 2001): DanbooruWikiImagePreview(
                    post_id=2001,
                    canonical_post_url="https://danbooru.donmai.us/posts/2001",
                    state=DanbooruImagePreviewState.READY,
                    local_path=None,
                    rating="g",
                    width=120,
                    height=156,
                ),
                ("post", 2002): DanbooruWikiImagePreview(
                    post_id=2002,
                    canonical_post_url="https://danbooru.donmai.us/posts/2002",
                    state=DanbooruImagePreviewState.READY,
                    local_path=None,
                    rating="g",
                    width=120,
                    height=156,
                ),
            }
        ),
        recent_posts_service=_StubRecentPostsResolver({"head_tilt": (2001, 2002)}),
        selection_text="head tilt",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    assert _dialog_contains_text(dialog, "Posts")
    post_cards = [
        card
        for card in dialog.findChildren(DanbooruWikiImageCard)
        if card._preview.post_id in {2001, 2002}
    ]
    assert {card._preview.post_id for card in post_cards} == {2001, 2002}


def test_danbooru_wiki_dialog_recent_posts_use_available_row_width(
    tmp_path: Path,
) -> None:
    """Recent-post galleries should not wrap early when a fifth tile still fits."""

    app = _app()
    image_path = tmp_path / "recent_post_preview.png"
    _write_image(image_path, width=120, height=156)
    recent_post_ids = (3001, 3002, 3003, 3004, 3005)
    dialog = DanbooruWikiDialog(
        wiki_service=_StubDanbooruWikiService(
            selection_results={
                "head tilt": _success_result(
                    _page_view(title="head_tilt", display_title="head tilt")
                )
            }
        ),
        image_preview_service=_StubImagePreviewResolver(
            {
                ("post", post_id): DanbooruWikiImagePreview(
                    post_id=post_id,
                    canonical_post_url=f"https://danbooru.donmai.us/posts/{post_id}",
                    state=DanbooruImagePreviewState.READY,
                    local_path=image_path,
                    rating="g",
                    width=120,
                    height=156,
                )
                for post_id in recent_post_ids
            }
        ),
        recent_posts_service=_StubRecentPostsResolver({"head_tilt": recent_post_ids}),
        selection_text="head tilt",
        lookup_dispatcher=_ImmediateDispatcher(),
    )
    dialog.show()
    app.processEvents()

    post_cards = [
        card
        for card in dialog.findChildren(DanbooruWikiImageCard)
        if card._preview.post_id in set(recent_post_ids)
    ]
    assert len(post_cards) == 5
    assert len({card.y() for card in post_cards}) == 1


def _success_result(
    page_view: DanbooruWikiContentPage,
) -> DanbooruWikiContentLookupResult:
    """Return one successful dialog lookup result."""

    return DanbooruWikiContentLookupResult(
        page=page_view,
        navigation_entry=DanbooruWikiNavigationEntry(
            title=page_view.title,
            display_title=page_view.display_title,
        ),
        requested_text=page_view.display_title,
        resolved_title=page_view.title,
    )


def _page_view(
    *,
    title: str = "long_hair",
    display_title: str = "long hair",
    body_dtext: str = (
        "h4. Definition\n\nHair that extends below the shoulders.\n\n"
        "See [[short_hair]]."
    ),
    other_names: tuple[str, ...] = ("long locks", "flowing hair"),
    category_name: str = "general",
) -> DanbooruWikiContentPage:
    """Return one representative page view for dialog tests."""

    return DanbooruWikiContentPage(
        title=title,
        display_title=display_title,
        category_name=category_name,
        post_count=5786,
        other_names=other_names,
        canonical_url=f"https://danbooru.donmai.us/wiki_pages/{title}",
        body_dtext=body_dtext,
        freshness_state=DanbooruContentFreshnessState.FRESH,
    )


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _record_opened_url(opened_urls: list[str], url: str) -> bool:
    """Record one externally opened URL for assertions and return success."""

    opened_urls.append(url)
    return True


def _widget_global_center(widget: QWidget) -> QPoint:
    """Return the global center point for one child widget."""

    return widget.mapToGlobal(widget.rect().center())


def _dialog_texts(dialog: DanbooruWikiDialog) -> tuple[str, ...]:
    """Return visible non-empty label texts below one dialog."""

    texts = [
        text for label in dialog.findChildren(QLabel) if (text := label.text().strip())
    ]
    texts.extend(
        text
        for view in dialog.findChildren(DanbooruWikiInlineFlow)
        if (text := view.plain_text().strip())
    )
    return tuple(texts)


def _dialog_contains_text(dialog: DanbooruWikiDialog, expected: str) -> bool:
    """Return whether any label below one dialog contains the expected text."""

    return any(expected in text for text in _dialog_texts(dialog))


def _first_inline_flow_with_text(
    dialog: DanbooruWikiDialog,
    expected_text: str,
) -> DanbooruWikiInlineFlow:
    """Return the first inline-flow widget containing the expected plain text."""

    return next(
        cast(DanbooruWikiInlineFlow, view)
        for view in dialog.findChildren(DanbooruWikiInlineFlow)
        if expected_text in view.plain_text()
    )


def _chipify_target(
    sections: tuple[DanbooruWikiSectionContent, ...],
    *,
    target_title: str,
    display_label: str,
    category_name: str,
) -> tuple[DanbooruWikiSectionContent, ...]:
    """Replace one wiki-link target with a resolved tag-chip node for tests."""

    def transform_nodes(
        nodes: tuple[DanbooruWikiInlineNode, ...],
    ) -> tuple[DanbooruWikiInlineNode, ...]:
        transformed: list[DanbooruWikiInlineNode] = []
        for node in nodes:
            if (
                isinstance(node, DanbooruWikiWikiLinkNode)
                and node.target_title == target_title
            ):
                transformed.append(
                    DanbooruWikiTagChipNode(
                        tag_name=target_title,
                        display_label=display_label,
                        category_name=category_name,
                    )
                )
                continue
            transformed.append(node)
        return tuple(transformed)

    resolved_sections: list[DanbooruWikiSectionContent] = []
    for section in sections:
        resolved_blocks: list[DanbooruWikiBlock] = []
        for block in section.blocks:
            if isinstance(block, DanbooruWikiParagraphBlock):
                resolved_blocks.append(
                    DanbooruWikiParagraphBlock(
                        inline_nodes=transform_nodes(block.inline_nodes)
                    )
                )
                continue
            if isinstance(block, DanbooruWikiQuoteBlock):
                resolved_blocks.append(
                    DanbooruWikiQuoteBlock(
                        inline_nodes=transform_nodes(block.inline_nodes)
                    )
                )
                continue
            if isinstance(block, DanbooruWikiListBlock):
                resolved_blocks.append(
                    DanbooruWikiListBlock(
                        ordered=block.ordered,
                        items=tuple(
                            DanbooruWikiListItem(
                                inline_nodes=transform_nodes(item.inline_nodes),
                                depth=item.depth,
                            )
                            for item in block.items
                        ),
                    )
                )
                continue
            resolved_blocks.append(
                DanbooruWikiImageReferenceBlock(
                    items=tuple(
                        DanbooruWikiImageReference(
                            source_kind=item.source_kind,
                            source_id=item.source_id,
                            caption_text=item.caption_text,
                            caption_nodes=transform_nodes(item.caption_nodes),
                        )
                        for item in block.items
                    )
                )
            )
        resolved_sections.append(
            DanbooruWikiSectionContent(
                heading=section.heading,
                blocks=tuple(resolved_blocks),
            )
        )
    return tuple(resolved_sections)


def _write_image(path: Path, *, width: int, height: int) -> None:
    """Write one solid-color PNG used for widget-size regression coverage."""

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ff66aa"))
    saved = image.save(str(path))
    assert saved is True
