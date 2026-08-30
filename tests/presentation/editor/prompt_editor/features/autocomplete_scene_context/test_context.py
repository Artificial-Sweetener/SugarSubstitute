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

"""Contract tests for Phase 27.5 autocomplete context owners."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)


from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteSceneContextController,
    PromptFeatureSnapshotIdentity,
)


class _SceneIdentityProvider:
    """Publish a deterministic scene identity for scene-context tests."""

    @property
    def scene_context_identity(self) -> PromptFeatureSnapshotIdentity:
        """Return the current scene feature identity."""

        return PromptFeatureSnapshotIdentity(
            source_revision=12,
            scene_context_id=("scene", "portrait"),
            cube_context_id=("cube", "alpha"),
        )


def test_phase27_scene_context_owner_prepares_effective_prompt_text_and_identity() -> (
    None
):
    """Scene context owner should prepare result context from source snapshots."""

    source = "<lora:global:1>\n**portrait\n<lora:portrait:1>\nmid\n**cafe\nmid"
    portrait_mid = source.index("mid")
    cafe_mid = source.rindex("mid")
    controller = PromptAutocompleteSceneContextController(
        scene_context_identity=lambda: _SceneIdentityProvider().scene_context_identity,
    )
    feature_identity = PromptFeatureSnapshotIdentity(feature_profile_id=("profile", 1))
    source_identity = PromptSourceIdentity(
        source_revision=4,
        source_length=len(source),
    )

    portrait_context = controller.context_for_tag_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=portrait_mid,
            word_end=portrait_mid + 3,
            active_tag_end=portrait_mid + 3,
        ),
        source_text=source,
        source_identity=source_identity,
        feature_profile_identity=feature_identity,
        query_identity=("tag", "portrait"),
    )
    cafe_context = controller.context_for_tag_query(
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=cafe_mid,
            word_end=cafe_mid + 3,
            active_tag_end=cafe_mid + 3,
        ),
        source_text=source,
        source_identity=source_identity,
        feature_profile_identity=feature_identity,
        query_identity=("tag", "cafe"),
    )

    assert "<lora:portrait:1>" in portrait_context.effective_prompt_text
    assert "<lora:portrait:1>" not in cafe_context.effective_prompt_text
    assert portrait_context.tag_context.source_text == source
    assert portrait_context.tag_context.effective_prompt_text == (
        portrait_context.effective_prompt_text
    )
    assert portrait_context.identity.source_revision == 4
    assert portrait_context.identity.feature_profile_id == ("profile", 1)
    assert portrait_context.identity.scene_context_id == ("scene", "portrait")
    assert portrait_context.identity.cube_context_id == ("cube", "alpha")
    assert (
        portrait_context.identity.query_identity != cafe_context.identity.query_identity
    )
