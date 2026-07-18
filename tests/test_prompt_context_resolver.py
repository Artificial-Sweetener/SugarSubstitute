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

"""Verify prompt context grouping uses typed sinks rather than authored guesses."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    PromptDetectionResult,
    PromptFieldLocator,
    PromptGraphContextResolver,
    PromptRole,
    PromptRoleDetection,
    PromptSinkLocator,
)


def _detection(
    node_name: str,
    role: PromptRole,
    *sinks: PromptSinkLocator,
) -> PromptRoleDetection:
    """Return one semantic prompt detection for context fixtures."""

    return PromptRoleDetection(
        locator=PromptFieldLocator(node_name, "text"),
        role=role,
        evidence=(),
        semantic_sinks=sinks,
    )


def test_context_resolver_groups_roles_only_at_the_same_sink_node() -> None:
    """Positive and negative fields should share context only at one typed anchor."""

    result = PromptDetectionResult(
        detections=(
            _detection(
                "positive",
                PromptRole.POSITIVE,
                PromptSinkLocator("sampler", "positive"),
            ),
            _detection(
                "negative",
                PromptRole.NEGATIVE,
                PromptSinkLocator("sampler", "negative"),
            ),
            _detection(
                "other_positive",
                PromptRole.POSITIVE,
                PromptSinkLocator("other_sampler", "positive"),
            ),
        )
    )

    contexts = PromptGraphContextResolver().resolve(result)

    assert len(contexts) == 1
    assert contexts[0].anchor_node_name == "sampler"
    assert contexts[0].positive_fields == (PromptFieldLocator("positive", "text"),)
    assert contexts[0].negative_fields == (PromptFieldLocator("negative", "text"),)


def test_context_resolver_does_not_pair_authored_only_prompt_roles() -> None:
    """Absent typed sinks, authored positive/negative cards remain unanchored."""

    result = PromptDetectionResult(
        detections=(
            _detection("positive", PromptRole.POSITIVE),
            _detection("negative", PromptRole.NEGATIVE),
        )
    )

    assert PromptGraphContextResolver().resolve(result) == ()
