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

"""Detect prompt wildcard placeholders that cannot resolve from the catalog."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.ports import (
    PromptWildcardCatalogGateway,
    PromptWildcardReference,
    PromptWildcardResolution,
)

from .prompt_diagnostics_models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptWildcardDiagnosticPayload,
)
from .prompt_diagnostics_service import PromptDiagnosticProviderResult
from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_views import PromptWildcardView


class PromptWildcardDiagnosticProvider:
    """Produce diagnostics for wildcard placeholders that do not resolve."""

    def __init__(
        self,
        wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        *,
        document_projector: PromptDocumentProjector | None = None,
    ) -> None:
        """Store collaborators used to parse and batch-resolve wildcard spans."""

        self._wildcard_catalog_gateway = wildcard_catalog_gateway
        self._document_projector = document_projector or PromptDocumentProjector()

    def diagnostics_for_text(self, text: str) -> PromptDiagnosticProviderResult:
        """Return missing-wildcard diagnostics for one prompt source string."""

        document_view = self._document_projector.build_document_view(text)
        if not document_view.wildcard_spans:
            return PromptDiagnosticProviderResult(diagnostics=())

        references = tuple(
            PromptWildcardReference(
                identifier=span.identifier,
                wildcard_form=span.wildcard_form,
                csv_column=span.csv_column,
                tag=span.tag,
            )
            for span in document_view.wildcard_spans
        )
        resolutions = self._wildcard_catalog_gateway.resolve_references(references)
        diagnostics = tuple(
            _diagnostic_for_missing_wildcard(span, resolution)
            for span, resolution in zip(
                document_view.wildcard_spans,
                resolutions,
                strict=True,
            )
            if not resolution.exists
        )
        return PromptDiagnosticProviderResult(diagnostics=diagnostics)


def _diagnostic_for_missing_wildcard(
    span: PromptWildcardView,
    resolution: PromptWildcardResolution,
) -> PromptDiagnostic:
    """Build one source-range diagnostic for an unresolved wildcard span."""

    csv_column_identity = "" if span.csv_column is None else span.csv_column
    payload = PromptWildcardDiagnosticPayload(
        identifier=span.identifier,
        wildcard_form=span.wildcard_form,
        csv_column=span.csv_column,
        matched_csv_column=resolution.matched_csv_column,
        available_csv_columns=resolution.available_csv_columns,
    )
    return PromptDiagnostic(
        diagnostic_id=(
            "wildcard:"
            f"{span.outer_start}:"
            f"{span.outer_end}:"
            f"{span.wildcard_form}:"
            f"{span.identifier}:"
            f"{csv_column_identity}"
        ),
        kind=PromptDiagnosticKind.WILDCARD,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=span.outer_start,
        source_end=span.outer_end,
        message=_missing_wildcard_message(span),
        payload=payload,
    )


def _missing_wildcard_message(span: PromptWildcardView) -> ApplicationText:
    """Return concise user-facing diagnostic text for one missing wildcard."""

    if span.wildcard_form == "csv" and span.csv_column is not None:
        return app_text(
            "Missing CSV wildcard column: %1:%2",
            span.identifier,
            span.csv_column,
        )
    return app_text("Missing wildcard: %1", span.identifier)


__all__ = ["PromptWildcardDiagnosticProvider"]
