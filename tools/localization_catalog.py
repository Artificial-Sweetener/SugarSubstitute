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

"""Extract and validate application-owned Qt presentation messages."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

_VISIBLE_METHODS = frozenset(
    {
        "addAction",
        "addItem",
        "begin",
        "insertTab",
        "setAccessibleDescription",
        "setAccessibleName",
        "setContent",
        "setDetailedText",
        "setInformativeText",
        "setHtml",
        "setLabelText",
        "setMarkdown",
        "setPlaceholderText",
        "setPlainText",
        "setStatusTip",
        "setText",
        "setTitle",
        "setToolTip",
        "setWindowTitle",
    }
)
_VISIBLE_CONSTRUCTORS = frozenset(
    {
        "BodyLabel",
        "CaptionLabel",
        "CheckBox",
        "CivitaiApiKeyTestResult",
        "CivitaiPreferenceSaveResult",
        "ComfyConnectionSaveResult",
        "ComfyConnectionSettingsSnapshot",
        "ComfyEnvironmentOperationFailure",
        "ComfyStartupIncident",
        "CubeLibraryOperationResult",
        "CubeLibraryReadinessView",
        "CubeLibraryStatusView",
        "CubePackBadgeView",
        "CubePackDetailView",
        "CubeRuntimeIssue",
        "ErrorReport",
        "FailedOutputImagePreparation",
        "GenerationFailure",
        "GenerationPreflightError",
        "GenerationPreviewSaveResult",
        "InfoLabel",
        "LocalizedBodyLabel",
        "LocalizedCaptionLabel",
        "LocalizedCheckBox",
        "LocalizedLabel",
        "LocalizedNativePushButton",
        "LocalizedPrimaryPushButton",
        "LocalizedPushButton",
        "LocalizedRadioButton",
        "LocalizedStrongBodyLabel",
        "LocalizedSubtitleLabel",
        "LocalizedTitleLabel",
        "ManagedTextAssetCreateAction",
        "ManagedComfyCleanupResult",
        "AttachedPythonRecoverySnapshot",
        "ManagedComfyStateCleanupResult",
        "ManagedProcessTerminationResult",
        "LazyMenuSubmenu",
        "MenuItem",
        "MenuModel",
        "MenuSection",
        "MenuSubmenu",
        "ModelMetadataMenuAction",
        "ModelMetadataMenuSubmenu",
        "PrimaryPushButton",
        "ProgressPresentation",
        "ReadinessIssuePresentation",
        "PromptContextMenuAction",
        "PromptDiagnostic",
        "PromptFeatureDefinition",
        "PromptPresetScopeOption",
        "PushButton",
        "QLabel",
        "QPushButton",
        "RadioButton",
        "SugarCubesMaintenanceDiagnostic",
        "OutputPreferenceSaveResult",
        "SettingsCard",
        "SettingsControlEntry",
        "SettingsNavigationDescriptor",
        "SettingsPageDescriptor",
        "SettingsPageEntry",
        "SettingsSectionEntry",
        "StrongBodyLabel",
        "SubtitleLabel",
        "SwitchButton",
        "TitleLabel",
        "ToolButton",
        "OnboardingFieldBlock",
        "OnboardingHeroPanel",
        "OnboardingInfoPanel",
        "OnboardingPageFrame",
        "OnboardingProvisioningFailure",
        "TargetModePresentation",
    }
)
_POSITIONAL_VISIBLE_CONSTRUCTORS = frozenset(
    {
        "BodyLabel",
        "CaptionLabel",
        "CheckBox",
        "CubePackDetailView",
        "InfoLabel",
        "LocalizedBodyLabel",
        "LocalizedCaptionLabel",
        "LocalizedCheckBox",
        "LocalizedLabel",
        "LocalizedNativePushButton",
        "LocalizedPrimaryPushButton",
        "LocalizedPushButton",
        "LocalizedRadioButton",
        "LocalizedStrongBodyLabel",
        "LocalizedSubtitleLabel",
        "LocalizedTitleLabel",
        "LazyMenuSubmenu",
        "MenuSubmenu",
        "ModelMetadataMenuAction",
        "ModelMetadataMenuSubmenu",
        "PrimaryPushButton",
        "PushButton",
        "QLabel",
        "QPushButton",
        "RadioButton",
        "StrongBodyLabel",
        "SubtitleLabel",
        "SwitchButton",
        "TitleLabel",
        "ToolButton",
    }
)
_POSITIONAL_VISIBLE_CALLS = _POSITIONAL_VISIBLE_CONSTRUCTORS | frozenset(
    {
        "append_log",
        "append_recovery_message",
        "fan_out",
        "on_log",
        "on_status",
        "_render_empty_detail",
        "_render_unavailable",
        "_set_library_message",
    }
)
_KEYWORD_VISIBLE_CALLS = _VISIBLE_CONSTRUCTORS | frozenset(
    {
        "_add_incident",
        "_report_error",
        "_show_exception_or_critical",
        "_show_exception_report",
        "_show_notification",
        "_show_status",
        "_set_copy",
        "error",
        "show_error_report",
        "warning",
    }
)
_VISIBLE_KEYWORDS = frozenset(
    {
        "content",
        "description",
        "detail_lines",
        "eyebrow",
        "helper",
        "helper_text",
        "headline",
        "label",
        "message",
        "meaning",
        "placeholder",
        "summary",
        "subtitle",
        "substitute_handles",
        "technical_note",
        "text",
        "title",
        "tooltip",
        "user_detail",
        "user_safe_detail",
        "user_message",
        "remediation_steps",
        "you_handle",
        "best_if",
    }
)
_APPLICATION_MESSAGE_FUNCTIONS = frozenset(
    {"app_text", "translate_application_message", "translate_application_text"}
)
_LANGUAGE_SELECTOR_MESSAGE_FUNCTIONS = frozenset({"translate_language_selector"})
_LAUNCHER_MESSAGE_FUNCTIONS = frozenset({"launcher_text"})
_MESSAGE_FUNCTIONS = (
    _APPLICATION_MESSAGE_FUNCTIONS
    | _LANGUAGE_SELECTOR_MESSAGE_FUNCTIONS
    | _LAUNCHER_MESSAGE_FUNCTIONS
)
_DIALOG_METHODS = frozenset({"critical", "information", "question", "warning"})
_FILE_DIALOG_METHODS = frozenset(
    {"getExistingDirectory", "getOpenFileName", "getOpenFileNames", "getSaveFileName"}
)
_PROPERTY_MESSAGE_FUNCTIONS = frozenset(
    {
        "set_localized_accessible_description",
        "set_localized_accessible_name",
        "set_localized_placeholder",
        "set_localized_text",
        "set_localized_tooltip",
        "set_localized_window_title",
    }
)
_PLACEHOLDER_PATTERN = re.compile(r"%\d+|\{[A-Za-z_][A-Za-z0-9_]*\}")
_HTML_TAG_PATTERN = re.compile(r"<[^>]*>")
_TRANSLATABLE_WORD_PATTERN = re.compile(r"[A-Za-z]{2,}")
_PRESENTATION_NAME_PATTERN = re.compile(
    r"(?:^|_)(?:text|title|label|description|tooltip|placeholder|heading|subtitle|"
    r"message|content|summary|helper|eyebrow|detail)(?:_|$)",
    re.IGNORECASE,
)
_NON_PRESENTATION_NAME_PATTERN = re.compile(
    r"(?:object_name|resource|path|url|id|key|role|style|qss|html|source|technical|"
    r"raw|diagnostic|log|filename|file_name|domain|owner|context|color|rgba|pattern|"
    r"mime|field_names|property|warmup|paint|cache|probe)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True, order=True)
class ExtractedMessage:
    """Describe one stable English source and its first source location."""

    source: str
    filename: str
    line: int


def extract_application_messages(project_root: Path) -> tuple[ExtractedMessage, ...]:
    """Return deterministic English sources from explicit application markers."""

    return _extract_messages(
        project_root,
        source_roots=_application_catalog_source_roots(project_root),
        message_functions=(
            _APPLICATION_MESSAGE_FUNCTIONS | _PROPERTY_MESSAGE_FUNCTIONS
        ),
    )


def extract_language_selector_messages(
    project_root: Path,
) -> tuple[ExtractedMessage, ...]:
    """Return shared language-selector sources owned by its Qt context."""

    return _extract_messages(
        project_root,
        source_roots=(project_root / "sugarsubstitute_shared" / "presentation",),
        message_functions=_LANGUAGE_SELECTOR_MESSAGE_FUNCTIONS,
    )


def extract_launcher_messages(project_root: Path) -> tuple[ExtractedMessage, ...]:
    """Return installer sources owned by the launcher Qt context."""

    return _extract_messages(
        project_root,
        source_roots=(project_root / "launcher" / "sugarsubstitute_launcher",),
        message_functions=_LAUNCHER_MESSAGE_FUNCTIONS,
    )


def _extract_messages(
    project_root: Path,
    *,
    source_roots: tuple[Path, ...],
    message_functions: frozenset[str],
) -> tuple[ExtractedMessage, ...]:
    """Extract deterministic source messages for one explicit owner."""

    locations: dict[str, tuple[str, int]] = {}
    for source_root in source_roots:
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            definitions = _message_definitions(tree)
            for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
                if _call_name(call) not in message_functions:
                    continue
                for candidate in _visible_candidates(call):
                    literals = _message_sources(candidate, definitions=definitions)
                    for literal in literals:
                        source = _normalize_source(literal)
                        if source:
                            locations.setdefault(
                                source,
                                (
                                    path.relative_to(project_root).as_posix(),
                                    call.lineno,
                                ),
                            )
    return tuple(
        ExtractedMessage(source, filename, line)
        for source, (filename, line) in sorted(locations.items())
    )


def find_unbound_dynamic_messages(
    project_root: Path,
) -> tuple[ExtractedMessage, ...]:
    """Return dynamic visible strings that bypass the localized-message API."""

    violations: list[ExtractedMessage] = []
    source_roots = _visible_source_roots(project_root)
    for source_root in source_roots:
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            definitions = _assignment_definitions(tree)
            for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
                if _call_name(call) in (
                    _MESSAGE_FUNCTIONS | _PROPERTY_MESSAGE_FUNCTIONS
                ):
                    continue
                for candidate in _unmarked_visible_expressions(
                    call, definitions=definitions
                ):
                    if not isinstance(candidate, ast.JoinedStr):
                        continue
                    source = _joined_source(candidate)
                    if source is not None:
                        violations.append(
                            ExtractedMessage(
                                source=source,
                                filename=path.relative_to(project_root).as_posix(),
                                line=call.lineno,
                            )
                        )
    return tuple(sorted(violations))


def find_unmarked_application_messages(
    project_root: Path,
) -> tuple[ExtractedMessage, ...]:
    """Return static visible English copy that lacks an explicit app marker."""

    violations: list[ExtractedMessage] = []
    source_roots = _visible_source_roots(project_root)
    allowed_functions = (
        _MESSAGE_FUNCTIONS
        | _PROPERTY_MESSAGE_FUNCTIONS
        | frozenset({"LocalizedSwitchButton"})
    )
    for source_root in source_roots:
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            definitions = _assignment_definitions(tree)
            for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
                if _call_name(call) in allowed_functions:
                    continue
                for candidate in _unmarked_visible_expressions(
                    call, definitions=definitions
                ):
                    if not (
                        isinstance(candidate, ast.Constant)
                        and isinstance(candidate.value, str)
                    ):
                        continue
                    source = _normalize_source(candidate.value)
                    if not source or not _TRANSLATABLE_WORD_PATTERN.search(source):
                        continue
                    violations.append(
                        ExtractedMessage(
                            source=source,
                            filename=path.relative_to(project_root).as_posix(),
                            line=call.lineno,
                        )
                    )
    return tuple(sorted(violations))


def find_unclassified_presentation_assignments(
    project_root: Path,
) -> tuple[ExtractedMessage, ...]:
    """Return indirect visible literals stored without an application marker."""

    violations: list[ExtractedMessage] = []
    for source_root in _application_source_roots(project_root):
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            enum_member_lines = _enum_member_assignment_lines(tree)
            for node in ast.walk(tree):
                target_and_value = _named_assignment(node)
                if target_and_value is None:
                    continue
                target_name, value = target_and_value
                if getattr(node, "lineno", -1) in enum_member_lines:
                    continue
                if not _PRESENTATION_NAME_PATTERN.search(target_name):
                    continue
                if _NON_PRESENTATION_NAME_PATTERN.search(target_name):
                    continue
                for source, line in _unmarked_assignment_literals(value):
                    normalized = _normalize_source(source)
                    if not normalized or not _TRANSLATABLE_WORD_PATTERN.search(
                        normalized
                    ):
                        continue
                    if _looks_like_technical_assignment_literal(normalized):
                        continue
                    violations.append(
                        ExtractedMessage(
                            source=normalized,
                            filename=path.relative_to(project_root).as_posix(),
                            line=line,
                        )
                    )
    return tuple(sorted(violations))


def find_unclassified_presentation_returns(
    project_root: Path,
) -> tuple[ExtractedMessage, ...]:
    """Return app-owned copy returned by presentation helpers without a marker."""

    violations: list[ExtractedMessage] = []
    for source_root in _application_source_roots(project_root):
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for function in (
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ):
                if not _PRESENTATION_NAME_PATTERN.search(function.name):
                    continue
                if _NON_PRESENTATION_NAME_PATTERN.search(function.name):
                    continue
                for node in ast.walk(function):
                    if not isinstance(node, ast.Return) or node.value is None:
                        continue
                    for source, line in _unmarked_assignment_literals(node.value):
                        normalized = _normalize_source(source)
                        if not normalized or not _TRANSLATABLE_WORD_PATTERN.search(
                            normalized
                        ):
                            continue
                        if _looks_like_technical_assignment_literal(normalized):
                            continue
                        violations.append(
                            ExtractedMessage(
                                source=normalized,
                                filename=path.relative_to(project_root).as_posix(),
                                line=line,
                            )
                        )
    return tuple(sorted(violations))


def _enum_member_assignment_lines(tree: ast.Module) -> frozenset[int]:
    """Return assignment lines owned by string-valued enum declarations."""

    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = {base.id for base in node.bases if isinstance(base, ast.Name)}
        if not base_names.intersection({"Enum", "StrEnum"}):
            continue
        lines.update(
            statement.lineno
            for statement in node.body
            if isinstance(statement, (ast.Assign, ast.AnnAssign))
        )
    return frozenset(lines)


def _looks_like_technical_assignment_literal(source: str) -> bool:
    """Return whether one token-shaped value is clearly an internal identifier."""

    if any(character.isspace() for character in source):
        return False
    if "_" in source or source.isupper():
        return True
    uppercase_count = sum(character.isupper() for character in source)
    return uppercase_count > 1


def placeholders(text: str) -> tuple[str, ...]:
    """Return ordered Qt and named-format placeholders from one message."""

    return tuple(_PLACEHOLDER_PATTERN.findall(text))


def pseudo_localize(source: str) -> str:
    """Expand one source into an unmistakable Unicode pseudo-localized string."""

    substitutions = str.maketrans(
        {
            "a": "à",
            "e": "ë",
            "i": "ï",
            "o": "ö",
            "u": "ü",
            "A": "Å",
            "E": "Ë",
            "I": "Ï",
            "O": "Ö",
            "U": "Ü",
        }
    )
    pieces: list[str] = []
    position = 0
    for match in _PLACEHOLDER_PATTERN.finditer(source):
        pieces.append(source[position : match.start()].translate(substitutions))
        pieces.append(match.group(0))
        position = match.end()
    pieces.append(source[position:].translate(substitutions))
    rendered = "".join(pieces)
    return f"⟦{rendered} ···⟧"


def _visible_literals(call: ast.Call) -> tuple[str, ...]:
    """Return static and numbered dynamic presentation source messages."""

    messages: list[str] = []
    for candidate in _visible_candidates(call):
        messages.extend(_message_sources(candidate))
    return tuple(messages)


def _application_source_roots(project_root: Path) -> tuple[Path, ...]:
    """Return source roots that can own application-visible messages."""

    return (
        project_root / "substitute" / "presentation",
        project_root / "substitute" / "application",
        project_root / "substitute" / "domain",
        project_root / "substitute" / "app" / "bootstrap",
    )


def _application_catalog_source_roots(project_root: Path) -> tuple[Path, ...]:
    """Return roots whose explicit markers feed the AppText catalog."""

    return (
        *_application_source_roots(project_root),
        project_root / "substitute" / "infrastructure",
    )


def _visible_source_roots(project_root: Path) -> tuple[Path, ...]:
    """Return roots whose explicit presentation calls can expose app copy."""

    return (
        *_application_catalog_source_roots(project_root),
        project_root / "launcher" / "sugarsubstitute_launcher",
        project_root / "sugarsubstitute_shared" / "presentation",
    )


def _named_assignment(node: ast.AST) -> tuple[str, ast.expr] | None:
    """Return a simple assignment target and value when statically inspectable."""

    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id, node.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is not None
    ):
        return node.target.id, node.value
    return None


def _assignment_definitions(tree: ast.Module) -> dict[str, ast.expr]:
    """Return simple definitions used to resolve indirect visible constants."""

    definitions: dict[str, ast.expr] = {}
    for node in tree.body:
        target_and_value = _named_assignment(node)
        if target_and_value is None:
            continue
        target_name, value = target_and_value
        definitions.setdefault(target_name, value)
    return definitions


def _message_definitions(tree: ast.Module) -> dict[str, ast.expr]:
    """Return module constants and loop aliases used by message-owner calls."""

    definitions = _assignment_definitions(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        iterator = node.iter
        if (
            isinstance(iterator, ast.Call)
            and _call_name(iterator) == "enumerate"
            and iterator.args
        ):
            iterator = iterator.args[0]
        if not isinstance(iterator, ast.Name) or iterator.id not in definitions:
            continue
        target_names = (
            (node.target.id,)
            if isinstance(node.target, ast.Name)
            else tuple(
                element.id
                for element in getattr(node.target, "elts", ())
                if isinstance(element, ast.Name)
            )
        )
        for target_name in target_names:
            definitions.setdefault(target_name, definitions[iterator.id])
    return definitions


def _unmarked_assignment_literals(expression: ast.expr) -> tuple[tuple[str, int], ...]:
    """Return literals in presentation data while skipping explicit markers."""

    if isinstance(expression, ast.Call):
        return ()
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return ((expression.value, expression.lineno),)
    if isinstance(expression, ast.JoinedStr):
        source = _joined_source(expression)
        return () if source is None else ((source, expression.lineno),)
    if isinstance(expression, ast.IfExp):
        return (
            *_unmarked_assignment_literals(expression.body),
            *_unmarked_assignment_literals(expression.orelse),
        )
    if isinstance(expression, ast.Dict):
        return tuple(
            item
            for value in expression.values
            for item in _unmarked_assignment_literals(value)
        )
    if isinstance(expression, (ast.List, ast.Set, ast.Tuple)):
        return tuple(
            item
            for element in expression.elts
            for item in _unmarked_assignment_literals(element)
        )
    if isinstance(expression, ast.BinOp):
        return (
            *_unmarked_assignment_literals(expression.left),
            *_unmarked_assignment_literals(expression.right),
        )
    return ()


def _message_sources(
    expression: ast.expr,
    *,
    definitions: dict[str, ast.expr] | None = None,
    resolving: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Extract every locale branch from one explicitly marked expression."""

    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return (expression.value,)
    if isinstance(expression, ast.JoinedStr):
        dynamic_source = _joined_source(expression)
        return () if dynamic_source is None else (dynamic_source,)
    if isinstance(expression, ast.IfExp):
        return (
            *_message_sources(
                expression.body,
                definitions=definitions,
                resolving=resolving,
            ),
            *_message_sources(
                expression.orelse,
                definitions=definitions,
                resolving=resolving,
            ),
        )
    if isinstance(expression, (ast.List, ast.Set, ast.Tuple)):
        return tuple(
            source
            for element in expression.elts
            for source in _message_sources(
                element,
                definitions=definitions,
                resolving=resolving,
            )
        )
    if (
        isinstance(expression, ast.Name)
        and definitions is not None
        and expression.id in definitions
        and expression.id not in resolving
    ):
        return _message_sources(
            definitions[expression.id],
            definitions=definitions,
            resolving=resolving | {expression.id},
        )
    return ()


def _visible_candidates(call: ast.Call) -> list[ast.expr]:
    """Return expression nodes occupying user-visible call positions."""

    name = _call_name(call)
    candidates: list[ast.expr] = []
    if (
        name in _DIALOG_METHODS
        and _call_owner_name(call) == "QMessageBox"
        and len(call.args) >= 3
    ):
        candidates.extend(call.args[1:3])
    elif name in _FILE_DIALOG_METHODS and _call_owner_name(call) == "QFileDialog":
        if len(call.args) >= 2:
            candidates.append(call.args[1])
        if name != "getExistingDirectory" and len(call.args) >= 4:
            candidates.append(call.args[3])
    elif (
        name == "addItem"
        and _call_receiver_attribute_name(call) == "_breadcrumb"
        and len(call.args) >= 2
    ):
        candidates.append(call.args[1])
    elif name in _VISIBLE_METHODS and call.args:
        candidates.append(call.args[0])
    if (
        _call_owner_name(call) == "InfoBadge"
        and name in {"custom", "error", "info", "success", "warning"}
        and call.args
    ):
        candidates.append(call.args[0])
    if _call_owner_name(call) == "TeachingTip" and name == "create":
        candidates.extend(
            keyword.value
            for keyword in call.keywords
            if keyword.arg in {"content", "title"}
        )
    if name in _MESSAGE_FUNCTIONS and call.args:
        candidates.append(call.args[0])
    if name in _PROPERTY_MESSAGE_FUNCTIONS and len(call.args) >= 2:
        candidates.append(call.args[1])
    if name == "set_fluent_tooltip_text" and len(call.args) >= 2:
        candidates.append(call.args[1])
    if name in {"LocalizedColorDialog", "LocalizedColorPickerButton"}:
        if len(call.args) >= 2:
            candidates.append(call.args[1])
        candidates.extend(
            keyword.value
            for keyword in call.keywords
            if keyword.arg in {"dialog_title", "title"}
        )
    if name in _POSITIONAL_VISIBLE_CALLS and call.args:
        candidates.append(call.args[0])
    if name in {"Action", "QAction"} and call.args:
        candidates.append(call.args[1] if len(call.args) >= 2 else call.args[0])
    if name == "MenuItem" and len(call.args) >= 2:
        candidates.append(call.args[1])
    if name in _KEYWORD_VISIBLE_CALLS or name == "__init__":
        candidates.extend(
            keyword.value
            for keyword in call.keywords
            if keyword.arg in _VISIBLE_KEYWORDS
        )
    return candidates


def _unmarked_visible_expressions(
    call: ast.Call,
    *,
    definitions: dict[str, ast.expr] | None = None,
) -> tuple[ast.expr, ...]:
    """Return visible literals while treating nested app markers as owned."""

    expressions: list[ast.expr] = []

    resolving: set[str] = set()

    def visit(expression: ast.expr) -> None:
        """Collect nested literals without crossing an explicit message marker."""

        if isinstance(expression, ast.Call):
            if _call_name(expression) in (
                _MESSAGE_FUNCTIONS | _PROPERTY_MESSAGE_FUNCTIONS
            ):
                return
            if (
                _call_name(expression) == "translate"
                and _call_owner_name(expression) == "QCoreApplication"
            ):
                return
        if isinstance(expression, (ast.Constant, ast.JoinedStr)):
            expressions.append(expression)
            return
        if (
            isinstance(expression, ast.Name)
            and definitions is not None
            and expression.id in definitions
            and expression.id not in resolving
        ):
            resolving.add(expression.id)
            visit(definitions[expression.id])
            resolving.remove(expression.id)
            return
        if isinstance(expression, ast.IfExp):
            visit(expression.body)
            visit(expression.orelse)
            return
        for child in ast.iter_child_nodes(expression):
            if isinstance(child, ast.expr):
                visit(child)

    for candidate in _visible_candidates(call):
        visit(candidate)
    return tuple(expressions)


def _joined_source(value: ast.JoinedStr) -> str | None:
    """Convert one translatable f-string to a numbered Qt source template."""

    parts: list[str] = []
    literal_parts: list[str] = []
    argument_index = 0
    for part in value.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            parts.append(part.value)
            literal_parts.append(part.value)
        elif isinstance(part, ast.FormattedValue):
            argument_index += 1
            parts.append(f"%{argument_index}")
    visible_literal = _HTML_TAG_PATTERN.sub("", "".join(literal_parts))
    if not _TRANSLATABLE_WORD_PATTERN.search(visible_literal):
        return None
    return "".join(parts)


def _call_name(call: ast.Call) -> str:
    """Return the terminal callable name without depending on import aliases."""

    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _call_owner_name(call: ast.Call) -> str:
    """Return the direct owner name for one attribute call when available."""

    if not isinstance(call.func, ast.Attribute):
        return ""
    owner = call.func.value
    if isinstance(owner, ast.Name):
        return owner.id
    return ""


def _call_receiver_attribute_name(call: ast.Call) -> str:
    """Return the terminal receiver attribute for one chained method call."""

    if not isinstance(call.func, ast.Attribute):
        return ""
    receiver = call.func.value
    if isinstance(receiver, ast.Attribute):
        return receiver.attr
    return ""


def _normalize_source(source: str) -> str:
    """Preserve visible content while rejecting blank and diagnostic-only literals."""

    if not source.strip():
        return ""
    return source.replace("\r\n", "\n")


__all__ = [
    "ExtractedMessage",
    "extract_application_messages",
    "extract_language_selector_messages",
    "extract_launcher_messages",
    "find_unbound_dynamic_messages",
    "find_unclassified_presentation_assignments",
    "find_unclassified_presentation_returns",
    "find_unmarked_application_messages",
    "placeholders",
    "pseudo_localize",
]
