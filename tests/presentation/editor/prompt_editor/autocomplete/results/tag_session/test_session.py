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

"""Verify tag autocomplete session result contracts."""

from __future__ import annotations


from types import SimpleNamespace
from typing import Any, cast

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
)
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
    PromptAutocompleteGhostTextSourceSnapshot,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession
from tests.support.prompt_editor.autocomplete_support import (
    build_test_autocomplete_stack,
)
from tests.support.prompt_editor.controller_support import (
    AutocompleteEditorDouble,
    MenuCursorDouble,
    TextAutocompleteEditorDouble,
    autocomplete_session_controller_with_session,
    import_autocomplete_module,
)


from tests.presentation.editor.prompt_editor.autocomplete.results.result_controller_support import (
    _Gateway,
    _mute_autocomplete_surfaces,
    _refresh_tag_result,
)


def test_coordinator_retains_selected_suggestion_when_result_still_matches() -> None:
    """Coordinator tag refresh keeps the selected row when the tag still exists."""

    mod = import_autocomplete_module()
    suggestions = (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
        PromptAutocompleteSuggestion("1girls", 3_424),
    )
    session_controller = autocomplete_session_controller_with_session(
        mod,
        AutocompleteSession(
            suggestions=(PromptAutocompleteSuggestion("1girls", 3_424),),
            selected_index=0,
            word_start=0,
            word_end=3,
            active_tag_end=3,
            prefix="1gi",
        ),
    )
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                SimpleNamespace(toPlainText=lambda: "1gi"),
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: suggestions
                ),
                autocomplete_session_controller=session_controller,
            ),
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="1gi",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text="1gi",
    )

    assert session_controller.session.suggestions == suggestions
    assert session_controller.session.selected_index == 1
    assert session_controller.session.word_start == 0
    assert session_controller.session.word_end == 3


def test_coordinator_clears_ghost_text_when_feature_disabled() -> None:
    """Disabling ghost text should keep autocomplete active and clear previews."""

    mod = import_autocomplete_module()
    editor = TextAutocompleteEditorDouble("1gi")
    publisher = PromptAutocompleteGhostTextPublisher(
        publish_preview_state=editor.set_autocomplete_preview_state
    )
    source_snapshot = PromptAutocompleteGhostTextSourceSnapshot(
        source_revision=0,
        source_length=3,
        cursor_position=3,
        source_text="1gi",
    )
    seed_session = AutocompleteSession(
        suggestions=(PromptAutocompleteSuggestion("1girl", 5_889_398),),
        selected_index=0,
        word_start=0,
        word_end=3,
        active_tag_end=3,
        prefix="1gi",
    )
    publisher.publish_for_session(seed_session, source_snapshot=source_snapshot)
    session_controller = mod.PromptAutocompleteSessionController()
    coordinator = build_test_autocomplete_stack(
        editor,
        prompt_autocomplete_gateway=_Gateway(
            {"1gi": (PromptAutocompleteSuggestion("1girl", 5_889_398),)}
        ),
        autocomplete_ghost_text_publisher=publisher,
        autocomplete_ghost_text_enabled=False,
        autocomplete_session_controller=session_controller,
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="1gi",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text="1gi",
    )

    assert editor.autocomplete_preview_updates[-1] is None
    assert session_controller.has_active_session()
    assert session_controller.session.suggestions == (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
    )


def test_coordinator_uses_prepared_source_text_snapshot() -> None:
    """Coordinator tag refresh should not read editor text while preparing results."""

    class _CountingTextEditor:
        """Count prompt text reads for one autocomplete refresh."""

        def __init__(self) -> None:
            """Initialize the editor text read counter."""

            self.reads = 0

        def toPlainText(self) -> str:
            """Return fixed prompt text while recording one read."""

            self.reads += 1
            return "1gi"

    editor = _CountingTextEditor()
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                editor,
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: (
                        PromptAutocompleteSuggestion("1girl", 5_889_398),
                    )
                ),
            ),
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="1gi",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text="1gi",
    )

    assert editor.reads == 0
    assert coordinator.session_controller.session.suggestions == (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
    )


def test_coordinator_falls_back_to_current_suffix_after_long_miss() -> None:
    """Long scene lines still complete the current tag when the full line misses."""

    source = "**scene\n" + ("background detail " * 10) + "1g"
    full_prefix = source[source.index("background") :]
    calls: list[str] = []
    suffix_suggestion = PromptAutocompleteSuggestion("1girl", 5_889_398)

    def search(
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return a suggestion only for the suffix fallback prefix."""

        calls.append(prefix)
        _ = limit
        return (suffix_suggestion,) if prefix == "1g" else ()

    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                TextAutocompleteEditorDouble(source),
                prompt_autocomplete_gateway=SimpleNamespace(search=search),
            ),
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix=full_prefix,
            word_start=source.index("background"),
            word_end=len(source),
            active_tag_end=len(source),
            fallback_query=PromptAutocompleteFallbackQuery(
                prefix="1g",
                word_start=source.rindex("1g"),
                word_end=len(source),
                active_tag_end=len(source),
            ),
        ),
        source_text=source,
    )

    assert calls == [full_prefix, "1g"]
    assert coordinator.session_controller.session.suggestions == (suffix_suggestion,)
    assert coordinator.session_controller.session.prefix == "1g"
    assert coordinator.session_controller.session.word_start == source.rindex("1g")
    assert coordinator.session_controller.session.word_end == len(source)
    assert coordinator.session_controller.session.active_tag_end == len(source)


def test_coordinator_preserves_matching_multi_word_tag_prefix() -> None:
    """Suffix fallback must not steal valid multi-word tag completions."""

    source = "long h"
    calls: list[str] = []
    suggestion = PromptAutocompleteSuggestion("long hair", 4_000_000)

    def search(
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return a match for the full multi-word prefix only."""

        calls.append(prefix)
        _ = limit
        return (suggestion,) if prefix == "long h" else ()

    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                TextAutocompleteEditorDouble(source),
                prompt_autocomplete_gateway=SimpleNamespace(search=search),
            ),
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="long h",
            word_start=0,
            word_end=len(source),
            active_tag_end=len(source),
        ),
        source_text=source,
    )

    assert calls == ["long h"]
    assert coordinator.session_controller.session.suggestions == (suggestion,)
    assert coordinator.session_controller.session.prefix == "long h"
    assert coordinator.session_controller.session.word_start == 0


def test_coordinator_filters_noop_tag_suggestions_before_opening_session() -> None:
    """Coordinator refresh suppresses suggestions that already match the query slice."""

    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_stack(
            AutocompleteEditorDouble(
                MenuCursorDouble(text="looking at viewer", position=17)
            ),
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: (
                    PromptAutocompleteSuggestion("looking_at_viewer", 500),
                )
            ),
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="looking at viewer",
            word_start=0,
            word_end=17,
            active_tag_end=17,
        ),
        source_text="looking at viewer",
    )

    assert coordinator.session_controller.session.suggestions == ()
