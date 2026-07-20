"""Enforce automatic localization and universal text-input source policies."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.localization_catalog import (
    find_unbound_dynamic_messages,
    find_unclassified_presentation_assignments,
    find_unclassified_presentation_returns,
    find_unmarked_application_messages,
)


@dataclass(frozen=True, slots=True, order=True)
class SourcePolicyViolation:
    """Describe one source construct that can restrict authored Unicode."""

    filename: str
    line: int
    reason: str


_TOOLTIP_ADAPTERS = frozenset(
    {
        Path("sugarsubstitute_shared/presentation/fluent_tooltips.py"),
        Path("sugarsubstitute_shared/presentation/localization/application_text.py"),
    }
)


def find_ascii_input_restrictions(
    project_root: Path,
) -> tuple[SourcePolicyViolation, ...]:
    """Find presentation code that explicitly restricts authored text to ASCII."""

    violations: list[SourcePolicyViolation] = []
    roots = (
        project_root / "substitute" / "presentation",
        project_root / "launcher" / "sugarsubstitute_launcher" / "ui",
    )
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
                reason = _ascii_restriction_reason(call)
                if reason is not None:
                    violations.append(
                        SourcePolicyViolation(
                            filename=path.relative_to(project_root).as_posix(),
                            line=call.lineno,
                            reason=reason,
                        )
                    )
    return tuple(sorted(violations))


def find_non_fluent_tooltip_usage(
    project_root: Path,
) -> tuple[SourcePolicyViolation, ...]:
    """Find tooltip construction or property writes outside the QFluent owner."""

    violations: list[SourcePolicyViolation] = []
    roots = (
        project_root / "substitute",
        project_root / "launcher" / "sugarsubstitute_launcher",
        project_root / "sugarsubstitute_shared",
    )
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            relative_path = path.relative_to(project_root)
            if relative_path in _TOOLTIP_ADAPTERS:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                reason = _tooltip_policy_reason(node)
                if reason is None:
                    continue
                violations.append(
                    SourcePolicyViolation(
                        filename=relative_path.as_posix(),
                        line=getattr(node, "lineno", 0),
                        reason=reason,
                    )
                )
    return tuple(sorted(violations))


def main() -> int:
    """Fail when UI copy or editable input bypasses localization policy."""

    project_root = Path(__file__).resolve().parents[1]
    failures = [
        f"{item.filename}:{item.line}: dynamic UI text bypasses localization: "
        f"{item.source}"
        for item in find_unbound_dynamic_messages(project_root)
    ]
    failures.extend(
        f"{item.filename}:{item.line}: visible app copy lacks app_text(): {item.source}"
        for item in find_unmarked_application_messages(project_root)
    )
    failures.extend(
        f"{item.filename}:{item.line}: indirect app copy lacks app_text(): {item.source}"
        for item in find_unclassified_presentation_assignments(project_root)
    )
    failures.extend(
        f"{item.filename}:{item.line}: returned app copy lacks app_text(): {item.source}"
        for item in find_unclassified_presentation_returns(project_root)
    )
    failures.extend(
        f"{item.filename}:{item.line}: {item.reason}"
        for item in find_ascii_input_restrictions(project_root)
    )
    failures.extend(
        f"{item.filename}:{item.line}: {item.reason}"
        for item in find_non_fluent_tooltip_usage(project_root)
    )
    if failures:
        print("\n".join(failures))
        return 1
    print("Localization source policy passed.")
    return 0


def _ascii_restriction_reason(call: ast.Call) -> str | None:
    """Return a policy reason for one explicit ASCII-only construct."""

    if isinstance(call.func, ast.Attribute):
        if call.func.attr == "isascii":
            return "isascii() cannot gate user-authored text"
        if (
            call.func.attr == "encode"
            and call.args
            and isinstance(call.args[0], ast.Constant)
            and str(call.args[0].value).lower() == "ascii"
        ):
            return "ASCII encoding cannot validate user-authored text"
    callable_name = _terminal_name(call.func)
    if callable_name not in {"QRegularExpression", "QRegExp"}:
        return None
    for argument in call.args:
        if (
            isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
            and any(token in argument.value for token in ("[A-Z", "[a-z", "[A-Za-z"))
        ):
            return "ASCII-letter regex cannot constrain a presentation input"
    return None


def _tooltip_policy_reason(node: ast.AST) -> str | None:
    """Return why one AST node bypasses the shared QFluent tooltip owner."""

    if isinstance(node, ast.ImportFrom):
        imported_names = {alias.name for alias in node.names}
        if "QToolTip" in imported_names:
            return "QToolTip imports bypass the shared QFluent tooltip owner"
        if imported_names & {"ToolTip", "ToolTipFilter"}:
            return "QFluent tooltip primitives may only be used by the shared owner"
        if node.module == "substitute.presentation.widgets.cursor_tooltip_filter":
            return "the retired cursor tooltip owner must not be imported"
        return None
    if not isinstance(node, ast.Call):
        return None
    callable_name = _terminal_name(node.func)
    if (
        callable_name == "getattr"
        and len(node.args) >= 2
        and _constant_string(node.args[1]) == "setToolTip"
    ):
        return "indirect setToolTip access must use the shared QFluent owner"
    if (
        callable_name == "setProperty"
        and node.args
        and (_constant_string(node.args[0]) or "").casefold() == "tooltip"
    ):
        return "tooltip property writes must use the shared QFluent owner"
    if callable_name == "setToolTip":
        return "setToolTip() must be routed through set_fluent_tooltip_text()"
    if callable_name in {"QToolTip", "ToolTip", "ToolTipFilter"}:
        return "tooltip widgets and filters may only be created by the shared owner"
    if callable_name in {"CursorToolTipFilter", "install_cursor_tooltip_filter"}:
        return "the retired cursor tooltip path must not be used"
    return None


def _terminal_name(expression: ast.expr) -> str:
    """Return the terminal callable name for one AST expression."""

    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        return expression.attr
    return ""


def _constant_string(expression: ast.expr) -> str | None:
    """Return one literal string value when present."""

    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value
    return None


if __name__ == "__main__":
    sys.exit(main())
