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

"""Verify wildcard and scene autocomplete result contracts."""

from __future__ import annotations


from types import SimpleNamespace
from typing import Any, cast

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.features.autocomplete_result_controller import (
    PromptAutocompleteResultController,
)
from substitute.presentation.editor.prompt_editor.features.catalog_snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
    PromptWildcardAutocompletePresentation,
)
from substitute.presentation.editor.prompt_editor.features.scene_models import (
    PromptSceneAutocompleteState,
)
from substitute.presentation.editor.prompt_editor.features.wildcard_models import (
    PromptWildcardAutocompleteQuerySnapshot,
)
from tests.support.prompt_editor.autocomplete_support import (
    build_test_autocomplete_stack,
)
from tests.support.prompt_editor.controller_support import (
    FakeWildcardRequestChannel,
    scene_feature,
)


from tests.presentation.editor.prompt_editor.autocomplete.results.result_controller_support import (
    _Gateway,
    _WildcardProvider,
    _mute_autocomplete_surfaces,
    _refresh_scene_result,
    _refresh_wildcard_result,
)


def test_coordinator_uses_wildcard_catalog_gateway() -> None:
    """Wildcard autocomplete presents prepared wildcard catalog rows."""

    suggestions = (
        PromptAutocompleteSuggestion(
            "animal",
            source_label="TXT wildcard",
            source_kind="wildcard",
        ),
    )
    calls: list[tuple[str, int]] = []

    class _WildcardCatalogGateway:
        """Record wildcard searches and return deterministic suggestions."""

        def search_wildcards(
            self,
            prefix: str,
            limit: int = 10,
        ) -> tuple[PromptAutocompleteSuggestion, ...]:
            """Return configured wildcard suggestions for the requested prefix."""

            calls.append((prefix, limit))
            return suggestions

    request_channel = FakeWildcardRequestChannel()
    wildcard_feature = PromptWildcardAutocompletePresentation(
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(
                (PromptEditorFeature.WILDCARD_AUTOCOMPLETE,)
            )
        ),
        wildcard_catalog_gateway=cast(
            PromptWildcardCatalogGateway,
            _WildcardCatalogGateway(),
        ),
        request_channel=request_channel,
    )
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                SimpleNamespace(toPlainText=lambda: "{"),
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: ()
                ),
                wildcard_feature=cast(Any, wildcard_feature),
            ),
        )
    )

    _refresh_wildcard_result(
        coordinator,
        PromptWildcardAutocompleteQuery(
            prefix="",
            opener_start=0,
            content_start=1,
            cursor_position=1,
            replacement_end=1,
        ),
    )

    assert calls == []
    assert coordinator.session_controller.session.mode == "none"
    assert len(request_channel.handles) == 1

    request_channel.handles[-1].run_work()

    assert calls == [("", 10)]
    assert coordinator.session_controller.session.mode == "wildcard"
    assert coordinator.session_controller.session.suggestions == suggestions
    assert coordinator.session_controller.session.word_start == 0


def test_coordinator_uses_authority_scene_titles() -> None:
    """Scene autocomplete searches workflow-provided authority scene names."""

    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                SimpleNamespace(toPlainText=lambda: "**p"),
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: ()
                ),
                scene_publication=scene_feature(
                    text="**p",
                    titles=("portrait", "cafe interior"),
                ),
            ),
        )
    )

    _refresh_scene_result(
        coordinator,
        PromptSceneAutocompleteQuery(
            prefix="p",
            marker_start=0,
            title_start=2,
            cursor_position=3,
            replacement_end=3,
        ),
    )

    assert coordinator.session_controller.session.mode == "scene"
    assert coordinator.session_controller.session.suggestions == (
        PromptAutocompleteSuggestion(
            "portrait",
            popularity=None,
            source_label="Scene",
            source_kind="scene",
        ),
    )
    assert coordinator.session_controller.session.word_start == 2


def test_coordinator_clears_scene_query_when_authority_titles_are_empty() -> None:
    """Scene autocomplete stays hidden when no reusable titles are configured."""

    coordinator = cast(
        Any,
        build_test_autocomplete_stack(
            SimpleNamespace(toPlainText=lambda: "**p"),
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: ()
            ),
            scene_publication=scene_feature(
                text="**p",
                titles=(),
            ),
        ),
    )
    _refresh_scene_result(
        coordinator,
        PromptSceneAutocompleteQuery(
            prefix="p",
            marker_start=0,
            title_start=2,
            cursor_position=3,
            replacement_end=3,
        ),
    )

    assert coordinator.session_controller.has_active_session() is False


def test_coordinator_filters_exact_scene_title_matches() -> None:
    """Scene autocomplete does not offer a no-op exact title replacement."""

    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                SimpleNamespace(toPlainText=lambda: "**portrait"),
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: ()
                ),
                scene_publication=scene_feature(
                    text="**portrait",
                    titles=("portrait", "portrait close"),
                ),
            ),
        )
    )

    _refresh_scene_result(
        coordinator,
        PromptSceneAutocompleteQuery(
            prefix="portrait",
            marker_start=0,
            title_start=2,
            cursor_position=10,
            replacement_end=10,
        ),
    )

    assert coordinator.session_controller.session.mode == "scene"
    assert [
        suggestion.tag
        for suggestion in coordinator.session_controller.session.suggestions
    ] == ["portrait close"]


def test_wildcard_and_scene_results_consume_prepared_feature_snapshots() -> None:
    """Wildcard and scene result paths adapt prepared feature rows into snapshots."""

    wildcard_query = PromptWildcardAutocompleteQuery(
        prefix="land",
        opener_start=0,
        content_start=1,
        cursor_position=5,
        replacement_end=6,
    )
    wildcard_snapshot = PromptWildcardAutocompleteQuerySnapshot(
        identity=CatalogSnapshotIdentity(query_identity=("wildcard", 1)),
        status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        prefix="land",
        limit=10,
        suggestions=(PromptAutocompleteSuggestion("landscape", 30),),
    )
    scene_query = PromptSceneAutocompleteQuery(
        prefix="in",
        marker_start=0,
        title_start=8,
        cursor_position=10,
        replacement_end=10,
    )
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=_Gateway({}),
        wildcard_feature=_WildcardProvider(wildcard_snapshot),
        scene_autocomplete_state=lambda: PromptSceneAutocompleteState(
            titles=("intro",),
            ready=True,
        ),
        limit=10,
    )

    wildcard_result = controller.result_for_wildcard_query(
        wildcard_query,
        source_identity=None,
    )
    scene_result = controller.result_for_scene_query(scene_query, source_identity=None)

    assert wildcard_result.status == "ready"
    assert wildcard_result.suggestions == (
        PromptAutocompleteSuggestion("landscape", 30),
    )
    assert wildcard_result.word_start == wildcard_query.opener_start
    assert scene_result.status == "ready"
    assert scene_result.suggestions == (
        PromptAutocompleteSuggestion(
            tag="intro",
            popularity=None,
            source_label="Scene",
            source_kind="scene",
        ),
    )
    assert scene_result.word_start == scene_query.title_start
