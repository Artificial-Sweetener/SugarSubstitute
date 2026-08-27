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

"""Provide deterministic localization ownership for unrelated widget tests."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QObject, Signal

from sugarsubstitute_shared.localization import (
    LanguageDefinition,
    LanguagePreference,
    load_language_manifest,
    render_source_application_text,
)
from sugarsubstitute_shared.presentation.localization import (
    LanguageSnapshot,
    TranslationManager,
)
from substitute.application.localization import NodePresentationService
from substitute.domain.localization import (
    NodeFieldPresentationRequest,
    NodePresentation,
    NodePresentationRequest,
    NodeTextCatalogSnapshot,
)


class StubTranslationManager(QObject):
    """Mimic committed language state without installing process translators."""

    languageChanged = Signal(object)

    def __init__(self, effective_language_identifier: str = "en") -> None:
        """Initialize automatic selection with one deterministic effective language."""

        super().__init__()
        self._languages = load_language_manifest().release_languages
        self._snapshot = LanguageSnapshot(
            requested=LanguagePreference.system(),
            effective_language_identifier=effective_language_identifier,
            formatting_locale="en_US",
            text_direction="left-to-right",
            revision=1,
            payload=None,
        )

    @property
    def available_languages(self) -> tuple[LanguageDefinition, ...]:
        """Return manifest-backed selector entries."""

        return self._languages

    @property
    def snapshot(self) -> LanguageSnapshot:
        """Return current deterministic state."""

        return self._snapshot

    def request_language(self, preference: LanguagePreference) -> LanguageSnapshot:
        """Commit one preference and notify test widgets synchronously."""

        effective_identifier = (
            self._snapshot.effective_language_identifier
            if preference.is_system
            else preference.language_identifier
        )
        self._snapshot = LanguageSnapshot(
            requested=preference,
            effective_language_identifier=effective_identifier,
            formatting_locale="en_US",
            text_direction="left-to-right",
            revision=self._snapshot.revision + 1,
            payload=None,
        )
        self.languageChanged.emit(self._snapshot)
        return self._snapshot


def stub_translation_manager() -> TranslationManager:
    """Return the structurally compatible test owner as its production type."""

    return cast(TranslationManager, StubTranslationManager())


def empty_node_presentation_service() -> NodePresentationService:
    """Return a deterministic technical-fallback node presentation owner."""

    snapshot = NodeTextCatalogSnapshot(
        effective_language_identifier="en",
        revision=1,
        active_layers=(),
        english_layers=(),
    )
    return NodePresentationService(
        lambda: snapshot,
        application_text_renderer=render_source_application_text,
    )


def technical_node_presentation(
    *,
    node_name: str,
    class_type: str,
    field_keys: tuple[str, ...] = (),
) -> NodePresentation:
    """Project deterministic technical fallback text for focused widget tests."""

    return empty_node_presentation_service().present(
        NodePresentationRequest(
            class_type=class_type,
            node_name=node_name,
            fields=tuple(
                NodeFieldPresentationRequest(field_key=field_key)
                for field_key in field_keys
            ),
        )
    )


__all__ = [
    "StubTranslationManager",
    "empty_node_presentation_service",
    "stub_translation_manager",
    "technical_node_presentation",
]
