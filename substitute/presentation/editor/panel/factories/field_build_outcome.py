"""Describe production field-build outcomes without sentinel interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EditorFieldBuildKind(StrEnum):
    """Classify every production field-factory result."""

    WIDGET = "widget"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    LAYOUT_HANDLED = "layout_handled"
    INTENTIONAL_ABSENCE = "intentional_absence"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class EditorFieldBuildOutcome:
    """Carry one typed field result, diagnostic reason, and preserved error."""

    kind: EditorFieldBuildKind
    surface: object | None = None
    reason: str = ""
    error: Exception | None = None

    @property
    def rendered(self) -> bool:
        """Return whether this outcome owns a usable field surface."""

        return self.kind in {
            EditorFieldBuildKind.WIDGET,
            EditorFieldBuildKind.EMPTY,
            EditorFieldBuildKind.UNAVAILABLE,
        }


__all__ = ["EditorFieldBuildKind", "EditorFieldBuildOutcome"]
