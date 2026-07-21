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

"""Tests for the managed text asset numbered prompt editor frame."""

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptScheduledLoraService,
    PromptSpellcheckSnapshot,
    wildcard_management_prompt_feature_profile,
)
from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetSourceSnapshot,
)
from substitute.presentation.managed_text_assets import NumberedPromptEditorFrame
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from tests.prompt_autocomplete_test_helpers import EmptyPromptAutocompleteGateway
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "prompt editor Qt frame tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_numbered_prompt_editor_frame_delegates_text_and_counts_lines() -> None:
    """The frame should keep source text ownership in the wrapped PromptEditor."""

    app = ensure_qapp()
    frame = _frame()
    frame.show()
    frame.setPlainText("first\nsecond\nthird")
    process_events(app)

    assert frame.toPlainText() == "first\nsecond\nthird"
    assert frame.line_count() == 3
    assert frame.formatted_line_number(0) == "01"
    assert frame.formatted_line_number(2) == "03"


def test_numbered_prompt_editor_frame_expands_gutter_after_99_lines() -> None:
    """The gutter should grow when source line numbers require more digits."""

    app = ensure_qapp()
    frame = _frame()
    frame.show()
    frame.setPlainText("\n".join(str(index) for index in range(99)))
    process_events(app)
    two_digit_width = frame.gutter_width()

    frame.setPlainText("\n".join(str(index) for index in range(100)))
    process_events(app)

    assert frame.formatted_line_number(99) == "100"
    assert frame.gutter_width() > two_digit_width


def test_numbered_prompt_editor_frame_uses_projection_source_line_geometry() -> None:
    """Zebra helpers should read visible logical lines from prompt projection geometry."""

    app = ensure_qapp()
    frame = _frame()
    frame.resize(520, 260)
    frame.show()
    frame.setPlainText("alpha\n{nested/hair}\nomega")
    process_events(app)

    source_line_rects = frame.editor().source_line_rects()

    assert tuple(rect.line_index for rect in source_line_rects)[:3] == (0, 1, 2)
    assert 1 in frame.zebra_line_indexes()
    assert frame._gutter.parent() is frame.editor()
    assert frame.editor().viewportMargins().left() == frame.gutter_width()
    assert frame._gutter.x() == frame.editor().contentsRect().left() - 4
    assert frame._gutter.width() > frame.gutter_width()
    assert (
        frame._gutter.x() + frame._gutter.width()
        == frame.editor().contentsRect().left() + frame.gutter_width()
    )
    assert frame.editor().cursorRect().left() < frame.editor().viewport().width()


def test_numbered_prompt_editor_frame_counts_trailing_empty_source_line() -> None:
    """A trailing newline should produce a separate final numbered row."""

    app = ensure_qapp()
    frame = _frame()
    frame.resize(520, 260)
    frame.show()
    frame.setPlainText("alpha\n")
    process_events(app)

    source_line_rects = frame.editor().source_line_rects()

    assert frame.line_count() == 2
    assert tuple(rect.line_index for rect in source_line_rects) == (0, 1)
    assert source_line_rects[1].rect.top() > source_line_rects[0].rect.top()


def test_wildcard_management_feature_profile_enables_all_prompt_features() -> None:
    """Wildcard management should expose the registry's normal prompt features."""

    profile = wildcard_management_prompt_feature_profile()

    assert all(profile.supports(feature) for feature in PromptEditorFeature)


def test_numbered_prompt_editor_forwards_complete_runtime_service_bundle() -> None:
    """Caller-neutral frames should wire every supplied prompt runtime service."""

    autocomplete = EmptyPromptAutocompleteGateway()
    wildcard = StaticPromptWildcardCatalogGateway({})
    danbooru_url_import = object()
    danbooru_wiki = object()
    danbooru_images = object()
    danbooru_posts = object()
    lora_catalog = _LoraCatalog()
    scheduled_lora = PromptScheduledLoraService()
    spellcheck = _SpellcheckService()
    thumbnails = object()
    metadata_actions = object()
    segments = _SegmentPresetSource()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record an external URL request."""

        opened_urls.append(url)
        return True

    frame = NumberedPromptEditorFrame(
        prompt_runtime_services=PromptEditorRuntimeServices(
            autocomplete_gateway=autocomplete,
            wildcard_catalog_gateway=wildcard,
            danbooru_url_import_service=cast(Any, danbooru_url_import),
            danbooru_wiki_service=cast(Any, danbooru_wiki),
            danbooru_image_preview_service=cast(Any, danbooru_images),
            danbooru_recent_posts_service=cast(Any, danbooru_posts),
            lora_catalog_service=cast(Any, lora_catalog),
            scheduled_lora_service=scheduled_lora,
            spellcheck_service=cast(Any, spellcheck),
            thumbnail_asset_repository=cast(Any, thumbnails),
            model_metadata_action_handler=cast(Any, metadata_actions),
            segment_preset_source=segments,
            open_url=open_url,
            prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
        ),
        prompt_feature_profile=wildcard_management_prompt_feature_profile(),
    )
    editor = cast(Any, frame.editor())

    assert editor._wildcard_feature_controller._wildcard_catalog_gateway is wildcard
    assert editor._danbooru_action_controller._url_import_service is danbooru_url_import
    assert editor._danbooru_action_controller._wiki_service is danbooru_wiki
    assert editor._danbooru_action_controller._image_preview_service is danbooru_images
    assert editor._danbooru_action_controller._recent_posts_service is danbooru_posts
    assert editor._lora_metadata_feature_controller._lora_catalog is lora_catalog
    assert editor._syntax_service._prompt_lora_catalog_service is lora_catalog
    assert (
        editor._lora_metadata_feature_controller._scheduled_lora_service
        is scheduled_lora
    )
    assert editor._diagnostics_feature_controller._spellcheck_service is spellcheck
    assert editor._lora_thumbnail_cache.asset_repository is thumbnails
    assert editor._segment_preset_controller._preset_source is segments
    assert editor._external_url_action_runner._open_url is open_url
    assert opened_urls == []


def _frame() -> NumberedPromptEditorFrame:
    """Create a numbered prompt editor frame with deterministic test gateways."""

    return NumberedPromptEditorFrame(
        prompt_runtime_services=PromptEditorRuntimeServices(
            autocomplete_gateway=EmptyPromptAutocompleteGateway(),
            wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
            prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
        ),
        prompt_feature_profile=wildcard_management_prompt_feature_profile(),
    )


class _SegmentPresetSource:
    """Provide an empty warm global segment catalog for runtime wiring tests."""

    def list_prompt_segment_presets(self) -> PromptSegmentPresetSourceSnapshot:
        """Return an empty prepared segment menu."""

        return PromptSegmentPresetSourceSnapshot(
            menu_model=PromptSegmentPresetMenuModel(),
            catalog_identity=CatalogSnapshotIdentity(catalog_revision=1),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        )

    def save_prompt_segment(self, **_kwargs: object) -> None:
        """Accept unused saves for the runtime wiring contract."""


class _SpellcheckService:
    """Provide an available empty spellcheck snapshot for editor construction."""

    @property
    def language_tag(self) -> str:
        """Return the test language tag."""

        return "en_US"

    def snapshot_for_text(self, text: str) -> PromptSpellcheckSnapshot:
        """Return an empty spelling snapshot for current source text."""

        return PromptSpellcheckSnapshot(
            source_text=text,
            language_tag=self.language_tag,
            issues=(),
        )


class _LoraCatalog:
    """Provide an empty prepared LoRA catalog for editor construction."""

    cache_revision = 1

    def cached_loras(self) -> tuple[object, ...]:
        """Return no cached LoRA rows."""

        return ()
