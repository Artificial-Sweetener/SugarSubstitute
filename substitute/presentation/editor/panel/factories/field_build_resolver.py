"""Convert raw field-factory behavior into typed, non-throwing outcomes."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.node_behavior import ResolvedFieldSpec

from .field_build_outcome import EditorFieldBuildKind, EditorFieldBuildOutcome


def resolve_editor_field_build(
    *,
    field_spec: ResolvedFieldSpec,
    build: Callable[[], object | None],
    layout_handled_sentinel: object,
) -> EditorFieldBuildOutcome:
    """Execute one raw factory call and preserve every outcome without raising."""

    try:
        result = build()
    except Exception as error:
        return EditorFieldBuildOutcome(
            kind=EditorFieldBuildKind.ERROR,
            reason="field_factory_exception",
            error=error,
        )
    return classify_editor_field_result(
        field_spec=field_spec,
        result=result,
        layout_handled_sentinel=layout_handled_sentinel,
    )


def classify_editor_field_result(
    *,
    field_spec: ResolvedFieldSpec,
    result: object | None,
    layout_handled_sentinel: object,
) -> EditorFieldBuildOutcome:
    """Describe a raw factory result through the shared production contract."""

    if result is layout_handled_sentinel:
        return EditorFieldBuildOutcome(kind=EditorFieldBuildKind.LAYOUT_HANDLED)
    if result is None:
        kind, reason = _missing_field_outcome(field_spec)
        return EditorFieldBuildOutcome(kind=kind, reason=reason)
    availability = _choice_availability(result)
    if availability == "empty":
        kind = EditorFieldBuildKind.EMPTY
    elif availability == "unavailable":
        kind = EditorFieldBuildKind.UNAVAILABLE
    else:
        kind = EditorFieldBuildKind.WIDGET
    return EditorFieldBuildOutcome(kind=kind, surface=result)


def _missing_field_outcome(
    field_spec: ResolvedFieldSpec,
) -> tuple[EditorFieldBuildKind, str]:
    """Distinguish expected socket/container absence from unsupported editors."""

    field_type = (field_spec.field_type or "").upper()
    if field_type == "COMFY_AUTOGROW_V3":
        return EditorFieldBuildKind.INTENTIONAL_ABSENCE, "autogrow_socket_container"
    value = field_spec.value
    if (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    ):
        return EditorFieldBuildKind.INTENTIONAL_ABSENCE, "connected_socket"
    if value is None and field_spec.meta_info.get("socketless") is not True:
        return EditorFieldBuildKind.INTENTIONAL_ABSENCE, "unconnected_socket"
    return EditorFieldBuildKind.UNSUPPORTED, "no_registered_field_factory"


def _choice_availability(surface: object) -> str:
    """Return the choice availability attached by the choice factory."""

    widget = surface[0] if isinstance(surface, tuple) and surface else surface
    property_getter = getattr(widget, "property", None)
    if not callable(property_getter):
        return ""
    availability = property_getter("choice_availability")
    return availability if isinstance(availability, str) else ""


__all__ = ["classify_editor_field_result", "resolve_editor_field_build"]
