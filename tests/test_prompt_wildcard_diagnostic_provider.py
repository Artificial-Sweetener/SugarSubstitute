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

"""Tests for missing prompt wildcard diagnostics."""

from __future__ import annotations

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.application.prompt_editor import (
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptWildcardDiagnosticPayload,
    PromptWildcardDiagnosticProvider,
)


class _RecordingWildcardGateway:
    """Resolve wildcard metadata from configured rows while recording batches."""

    def __init__(
        self,
        resolutions_by_reference: dict[
            tuple[str, str, str | None],
            PromptWildcardResolution,
        ],
    ) -> None:
        """Store deterministic wildcard resolutions."""

        self._resolutions_by_reference = dict(resolutions_by_reference)
        self.calls: list[tuple[PromptWildcardReference, ...]] = []

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Record one batch and return configured resolution rows."""

        self.calls.append(references)
        return tuple(
            self._resolutions_by_reference.get(
                (
                    reference.identifier,
                    reference.wildcard_form,
                    reference.csv_column,
                ),
                PromptWildcardResolution(
                    identifier=reference.identifier,
                    wildcard_form=reference.wildcard_form,
                    csv_column=reference.csv_column,
                    exists=False,
                ),
            )
            for reference in references
        )

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no autocomplete suggestions."""

        _ = (prefix, limit)
        return ()


def test_wildcard_diagnostic_provider_reports_missing_simple_wildcard() -> None:
    """Missing simple placeholders should produce one source-range diagnostic."""

    provider = PromptWildcardDiagnosticProvider(_RecordingWildcardGateway({}))
    result = provider.diagnostics_for_text("prefix {missing|2} suffix")

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.kind is PromptDiagnosticKind.WILDCARD
    assert diagnostic.severity is PromptDiagnosticSeverity.ERROR
    assert (diagnostic.source_start, diagnostic.source_end) == (7, 18)
    assert diagnostic.message == "Missing wildcard: missing"
    assert diagnostic.diagnostic_id == "wildcard:7:18:simple:missing:"
    assert isinstance(diagnostic.payload, PromptWildcardDiagnosticPayload)
    assert diagnostic.payload.identifier == "missing"
    assert diagnostic.payload.wildcard_form == "simple"
    assert diagnostic.payload.csv_column is None


def test_wildcard_diagnostic_provider_ignores_existing_simple_wildcard() -> None:
    """Existing simple placeholders should not produce diagnostics."""

    gateway = _RecordingWildcardGateway(
        {
            ("animal", "simple", None): PromptWildcardResolution(
                identifier="animal",
                wildcard_form="simple",
                exists=True,
            )
        }
    )
    provider = PromptWildcardDiagnosticProvider(gateway)

    result = provider.diagnostics_for_text("{animal}")

    assert result.diagnostics == ()


def test_wildcard_diagnostic_provider_reports_missing_csv_column() -> None:
    """Missing CSV columns should include CSV metadata in the diagnostic payload."""

    gateway = _RecordingWildcardGateway(
        {
            ("monster", "csv", "color"): PromptWildcardResolution(
                identifier="monster",
                wildcard_form="csv",
                csv_column="color",
                exists=False,
                available_csv_columns=("Size", "Mood"),
            )
        }
    )
    provider = PromptWildcardDiagnosticProvider(gateway)

    result = provider.diagnostics_for_text("{csv:monster:color}")

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.message == "Missing CSV wildcard column: monster:color"
    assert isinstance(diagnostic.payload, PromptWildcardDiagnosticPayload)
    assert diagnostic.payload.identifier == "monster"
    assert diagnostic.payload.wildcard_form == "csv"
    assert diagnostic.payload.csv_column == "color"
    assert diagnostic.payload.available_csv_columns == ("Size", "Mood")


def test_wildcard_diagnostic_provider_ignores_existing_csv_column() -> None:
    """Existing CSV wildcard columns should not produce diagnostics."""

    gateway = _RecordingWildcardGateway(
        {
            ("monster", "csv", "color"): PromptWildcardResolution(
                identifier="monster",
                wildcard_form="csv",
                csv_column="color",
                exists=True,
                matched_csv_column="Color",
                available_csv_columns=("Color", "Size"),
            )
        }
    )
    provider = PromptWildcardDiagnosticProvider(gateway)

    result = provider.diagnostics_for_text("{csv:monster:color}")

    assert result.diagnostics == ()


def test_wildcard_diagnostic_provider_resolves_multiple_spans_in_one_batch() -> None:
    """Provider should batch wildcard resolution for one prompt snapshot."""

    gateway = _RecordingWildcardGateway({})
    provider = PromptWildcardDiagnosticProvider(gateway)

    result = provider.diagnostics_for_text("{missing}, {csv:monster:color|2}")

    assert len(result.diagnostics) == 2
    assert len(gateway.calls) == 1
    assert [
        (
            reference.identifier,
            reference.wildcard_form,
            reference.csv_column,
            reference.tag,
        )
        for reference in gateway.calls[0]
    ] == [
        ("missing", "simple", None, None),
        ("monster", "csv", "color", "2"),
    ]
    assert [(item.source_start, item.source_end) for item in result.diagnostics] == [
        (0, 9),
        (11, 32),
    ]


def test_wildcard_diagnostic_provider_skips_gateway_without_wildcards() -> None:
    """Prompts without wildcard spans should avoid catalog resolution work."""

    gateway = _RecordingWildcardGateway({})
    provider = PromptWildcardDiagnosticProvider(gateway)

    result = provider.diagnostics_for_text("plain prompt")

    assert result.diagnostics == ()
    assert gateway.calls == []
