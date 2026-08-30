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

"""Observe production field-factory behavior without changing its result."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from time import perf_counter
from types import TracebackType
from typing import cast

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.presentation.editor.panel import node_card_builder
from substitute.presentation.editor.panel.factories.field_build_resolver import (
    classify_editor_field_result,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    LAYOUT_HANDLED,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.models import (
    FieldFactoryObservation,
)


class ProductionFieldFactoryObserver:
    """Wrap the production field entry point and preserve its real result."""

    def __init__(self) -> None:
        """Initialize an uninstalled observer with no recorded calls."""

        self._original: Callable[..., object] | None = None
        self._observations: list[FieldFactoryObservation] = []

    def __enter__(self) -> ProductionFieldFactoryObserver:
        """Install the passive wrapper around the builder module's imported entry."""

        if self._original is not None:
            raise RuntimeError("Production field observer is already installed.")
        original = cast(
            Callable[..., object],
            getattr(node_card_builder, "build_widget_for_field_spec"),
        )
        self._original = original

        def observed_build_widget_for_field_spec(
            *args: object,
            **kwargs: object,
        ) -> object:
            """Call production unchanged while recording its result or exception."""

            field_spec = kwargs.get("field_spec")
            if not isinstance(field_spec, ResolvedFieldSpec):
                return original(*args, **kwargs)
            started_at = perf_counter()
            try:
                result = original(*args, **kwargs)
            except Exception as error:
                self._observations.append(
                    self._observation(
                        field_spec,
                        result="exception",
                        elapsed_ms=(perf_counter() - started_at) * 1000.0,
                        exception=error,
                        traceback_text=traceback.format_exc(),
                    )
                )
                raise
            outcome = classify_editor_field_result(
                field_spec=field_spec,
                result=result,
                layout_handled_sentinel=LAYOUT_HANDLED,
            )
            result_name = outcome.kind.value
            if outcome.rendered:
                result_name = "widget_built"
                widget = result[0] if isinstance(result, tuple) else result
                widget_type = type(widget).__name__
            else:
                widget_type = ""
            self._observations.append(
                self._observation(
                    field_spec,
                    result=result_name,
                    widget_type=widget_type,
                    elapsed_ms=(perf_counter() - started_at) * 1000.0,
                )
            )
            return result

        setattr(
            node_card_builder,
            "build_widget_for_field_spec",
            observed_build_widget_for_field_spec,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Restore the exact production entry point after observation."""

        del exc_type, exc, tb
        original = self._original
        self._original = None
        if original is not None:
            setattr(node_card_builder, "build_widget_for_field_spec", original)

    def reset(self) -> None:
        """Discard observations from the previously completed workflow."""

        self._observations.clear()

    def observations(self) -> tuple[FieldFactoryObservation, ...]:
        """Return the calls recorded for the current workflow."""

        return tuple(self._observations)

    @staticmethod
    def _observation(
        field_spec: ResolvedFieldSpec,
        *,
        result: str,
        elapsed_ms: float,
        widget_type: str = "",
        exception: Exception | None = None,
        traceback_text: str = "",
    ) -> FieldFactoryObservation:
        """Build one immutable observation from a production field contract."""

        behavior = field_spec.field_behavior
        return FieldFactoryObservation(
            node_id=field_spec.node_name,
            class_type=field_spec.class_type,
            field_key=field_spec.field_key,
            field_type=field_spec.field_type or "",
            presentation=behavior.presentation.value,
            control_name=behavior.control_name or "",
            value_source=field_spec.value_source.value,
            result=result,
            widget_type=widget_type,
            exception_type=type(exception).__name__ if exception is not None else "",
            exception_message=str(exception) if exception is not None else "",
            traceback=traceback_text,
            elapsed_ms=elapsed_ms,
        )
