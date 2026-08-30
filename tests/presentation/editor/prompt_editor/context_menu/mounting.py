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

"""Mount live prompt editors for independent context-menu capability tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import cast

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.execution import immediate_prompt_task_executor_factory
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)


def ensure_qapp() -> QApplication:
    """Return the running Qt application for prompt-editor widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(_app: QApplication) -> None:
    """Deliver callbacks queued by the preceding prompt-editor operation."""

    wait_for_queued_qt_turn()


def wait_for_prompt_editor_projection(editor: PromptEditor) -> None:
    """Wait until a mounted editor has current projection state and geometry."""

    wait_for_qt_condition(
        lambda: (
            editor.viewport().width() > 0 and not editor.has_pending_projection_update()
        )
    )


@pytest.fixture()
def prompt_widgets() -> Iterator[list[QWidget]]:
    """Track and dispose widgets created by one context-menu contract test."""

    widgets: list[QWidget] = []
    yield widgets
    app = ensure_qapp()
    for widget in reversed(widgets):
        widget.close()
        widget.deleteLater()
    process_events(app)


def create_prompt_editor(prompt_widgets: list[QWidget]) -> PromptEditor:
    """Create and show a standard prompt editor with stable geometry."""

    ensure_qapp()
    host = QWidget()
    host.resize(440, 220)
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_feature_profile=PromptEditorFeatureProfile.enabled_profile(
            (
                PromptEditorFeature.EMPHASIS,
                PromptEditorFeature.WILDCARD_SYNTAX,
                PromptEditorFeature.WILDCARD_AUTOCOMPLETE,
            )
        ),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setFocus()
    editor.replaceBaselineSourceText("alpha beta gamma")
    wait_for_prompt_editor_projection(editor)
    prompt_widgets.extend([host, editor])
    return editor


class _EmptyLoraCatalog:
    """Provide a no-op LoRA catalog for context-menu mounting."""

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return no LoRA rows."""

        return ()

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return no cached LoRA rows."""

        return ()

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return no LoRA match for an empty catalog."""

        _ = prompt_name
        return None


def create_lora_prompt_editor(prompt_widgets: list[QWidget]) -> PromptEditor:
    """Create a prompt editor configured with LoRA catalog support."""

    return create_lora_prompt_editor_with_resolver(prompt_widgets)


def create_lora_prompt_editor_with_resolver(
    prompt_widgets: list[QWidget],
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
    | None = None,
) -> PromptEditor:
    """Create a LoRA-aware editor with an optional scheduled-LoRA resolver."""

    ensure_qapp()
    host = QWidget()
    host.resize(440, 220)
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        prompt_lora_catalog_service=_EmptyLoraCatalog(),
        scheduled_lora_resolver=scheduled_lora_resolver,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setFocus()
    editor.replaceBaselineSourceText("alpha beta gamma")
    wait_for_prompt_editor_projection(editor)
    prompt_widgets.extend([host, editor])
    return editor
