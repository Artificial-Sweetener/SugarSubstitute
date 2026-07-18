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

"""Define typed node-behavior models shared across domain, application, and adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping


class CardMode(StrEnum):
    """Enumerate supported node-card presentation modes."""

    STANDARD = "standard"
    PROMPT = "prompt"


class CollapseMode(StrEnum):
    """Enumerate card collapse policies."""

    AUTO = "auto"
    EXEMPT = "exempt"


class EnabledSwitchPolicy(StrEnum):
    """Enumerate title-switch visibility policies."""

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


class ActivationSwitchSource(StrEnum):
    """Enumerate ownership sources for activation-switch policy decisions."""

    DEFAULT = "default"
    HOST = "host"
    DECLARATIVE = "declarative"
    HOOK = "hook"
    RUNTIME = "runtime"
    INFERRED = "inferred"


class ActivationSwitchRole(StrEnum):
    """Enumerate inferred semantic roles for graph-aware activation switches."""

    NONE = "none"
    TYPED_TRANSFORM = "typed_transform"
    SAMPLER_WORKER = "sampler_worker"


class ActivationDefault(StrEnum):
    """Enumerate policy-controlled node activation defaults."""

    AUTO = "auto"
    ENABLED = "enabled"
    DISABLED = "disabled"


class FieldPresentation(StrEnum):
    """Enumerate field-level control presentation modes."""

    STANDARD = "standard"
    PROMPT_BOX = "prompt_box"
    IMAGE_PICKER = "image_picker"
    MASK_PICKER = "mask_picker"
    MODEL_PICKER = "model_picker"
    SEED_BOX = "seed_box"
    CUSTOM = "custom"


class PromptRole(StrEnum):
    """Enumerate semantic prompt roles exposed by cube-authored prompt nodes."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class RowMode(StrEnum):
    """Enumerate supported field row layouts."""

    INLINE = "inline"
    FULL_WIDTH = "full_width"


class LabelMode(StrEnum):
    """Enumerate field label treatment options."""

    STANDARD = "standard"
    PROMPT = "prompt"
    HIDDEN = "hidden"


class OverridePinPolicy(StrEnum):
    """Enumerate workflow-toolbar pinning policies for one field."""

    NEVER = "never"
    OPTIONAL = "optional"
    DEFAULT_PINNED = "default_pinned"


class VisibilityRule(StrEnum):
    """Enumerate runtime card-visibility policies."""

    DEFAULT = "default"
    ONLY_FIRST_OF_CLASS = "only_first_of_class"
    ONLY_FIRST_DISTINCT_CHECKPOINT = "only_first_distinct_checkpoint"


class RevealMode(StrEnum):
    """Enumerate reveal-menu participation policies."""

    NONE = "none"
    MENU = "menu"


class TitleControl(StrEnum):
    """Enumerate optional controls rendered in the node-card title row."""

    ENABLED_SWITCH = "enabled_switch"
    NODE_LINK_SELECTOR = "node_link_selector"
    PROMPT_LINK_SELECTOR = "prompt_link_selector"


@dataclass(frozen=True)
class OverrideBehavior:
    """Describe workflow-toolbar override behavior for one resolved field."""

    override_key: str | None = None
    pin_policy: OverridePinPolicy = OverridePinPolicy.NEVER
    toolbar_label_override: str | None = None
    toolbar_order: int | None = None


@dataclass(frozen=True)
class PromptFieldBehavior:
    """Describe prompt semantics attached to one resolved field."""

    role: PromptRole
    linkable: bool = True


@dataclass(frozen=True)
class FieldBehavior:
    """Describe resolved field behavior consumed by presentation renderers."""

    field_key: str
    presentation: FieldPresentation = FieldPresentation.STANDARD
    control_name: str | None = None
    row_mode: RowMode = RowMode.INLINE
    label_mode: LabelMode = LabelMode.STANDARD
    label_override: str | None = None
    column_span: int | None = None
    style: Mapping[str, object] = field(default_factory=dict)
    hidden: bool = False
    override_behavior: OverrideBehavior = field(default_factory=OverrideBehavior)
    prompt: PromptFieldBehavior | None = None


@dataclass(frozen=True)
class CardBehavior:
    """Describe resolved card behavior consumed by presentation renderers."""

    card_mode: CardMode = CardMode.STANDARD
    collapse_mode: CollapseMode = CollapseMode.AUTO
    enabled_switch_policy: EnabledSwitchPolicy = EnabledSwitchPolicy.AUTO
    enabled_switch_source: ActivationSwitchSource = ActivationSwitchSource.DEFAULT
    activation_switch_role: ActivationSwitchRole = ActivationSwitchRole.NONE
    activation_signal_types: frozenset[str] = field(default_factory=frozenset)
    activation_default: ActivationDefault = ActivationDefault.AUTO
    visibility_rule: VisibilityRule = VisibilityRule.DEFAULT
    reveal_mode: RevealMode = RevealMode.NONE
    icon_name: str | None = None
    title_controls: tuple[TitleControl, ...] = ()
    hidden: bool = False
    force_visible: bool = False
    tooltip: str | None = None


@dataclass(frozen=True)
class ResolvedNodeBehavior:
    """Describe the fully resolved behavior contract for one cube/node."""

    node_name: str
    class_type: str
    card: CardBehavior
    fields: Mapping[str, FieldBehavior]
    display_name: str | None = None
    field_groups: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class FieldBehaviorPatch:
    """Describe a partial field-behavior override."""

    presentation: FieldPresentation | None = None
    control_name: str | None = None
    row_mode: RowMode | None = None
    label_mode: LabelMode | None = None
    label_override: str | None = None
    column_span: int | None = None
    style: Mapping[str, object] | None = None
    hidden: bool | None = None
    override_behavior: OverrideBehaviorPatch | None = None
    prompt: PromptFieldBehaviorPatch | None = None


@dataclass(frozen=True)
class OverrideBehaviorPatch:
    """Describe a partial workflow-toolbar override behavior patch."""

    override_key: str | None = None
    pin_policy: OverridePinPolicy | None = None
    toolbar_label_override: str | None = None
    toolbar_order: int | None = None


@dataclass(frozen=True)
class PromptFieldBehaviorPatch:
    """Describe a partial prompt-field behavior patch."""

    role: PromptRole | None = None
    linkable: bool | None = None


@dataclass(frozen=True)
class CardBehaviorPatch:
    """Describe a partial card-behavior override."""

    card_mode: CardMode | None = None
    collapse_mode: CollapseMode | None = None
    enabled_switch_policy: EnabledSwitchPolicy | None = None
    enabled_switch_source: ActivationSwitchSource | None = None
    activation_switch_role: ActivationSwitchRole | None = None
    activation_signal_types: frozenset[str] | None = None
    activation_default: ActivationDefault | None = None
    visibility_rule: VisibilityRule | None = None
    reveal_mode: RevealMode | None = None
    icon_name: str | None = None
    title_controls: tuple[TitleControl, ...] | None = None
    hidden: bool | None = None
    force_visible: bool | None = None


@dataclass(frozen=True)
class NodeBehaviorPatch:
    """Describe a partial node-behavior override for one class or named node."""

    card: CardBehaviorPatch = field(default_factory=CardBehaviorPatch)
    field_patches: Mapping[str, FieldBehaviorPatch] = field(default_factory=dict)
    field_groups: tuple[tuple[str, ...], ...] | None = None


@dataclass(frozen=True)
class PackageBehaviorPatch:
    """Describe declarative or hook-supplied behavior for one package instance."""

    by_class: Mapping[str, NodeBehaviorPatch] = field(default_factory=dict)
    by_node: Mapping[str, NodeBehaviorPatch] = field(default_factory=dict)
    by_node_instance: Mapping[str, NodeBehaviorPatch] = field(default_factory=dict)
    hidden_strings: frozenset[str] = frozenset()
    hidden_class_types: frozenset[str] = frozenset()
    hidden_node_names: frozenset[str] = frozenset()
    hidden_fields_by_node: Mapping[str, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class NodeBehaviorContext:
    """Describe the inputs required to resolve behavior for one node instance."""

    stack_order: tuple[str, ...]
    cube_alias: str
    node_name: str
    class_type: str
    node_title: str | None
    live_node_definition: Mapping[str, object] | None
    declarative_patch: PackageBehaviorPatch | None
    hook_patch: PackageBehaviorPatch | None
    workflow_overrides: Mapping[str, object]
    node_instance_patch: NodeBehaviorPatch | None
    graph_inference_patch: NodeBehaviorPatch | None = None


@dataclass(frozen=True)
class NodeActivationPolicy:
    """Describe one node's policy-derived activation defaults before user override."""

    default_active: bool
    default_visible: bool
    revealable: bool
    show_enabled_switch: bool
    hidden_reason: str | None = None


@dataclass(frozen=True)
class NodeActivationOverride:
    """Describe one persisted explicit activation override from the workflow buffer."""

    explicit_enabled: bool | None = None


@dataclass(frozen=True)
class NodeVisibilityOverride:
    """Describe one persisted explicit editor reveal override."""

    explicit_revealed: bool | None = None


@dataclass(frozen=True)
class NodeDisplayDecision:
    """Describe the resolved node display state consumed by the editor UI."""

    visible: bool
    enabled: bool
    reason: str
    revealable: bool = False
    reveal_checked: bool = False
    show_enabled_switch: bool = False
    policy_default_enabled: bool = True
    policy_default_visible: bool = True
    explicit_override: bool | None = None
    explicit_revealed: bool | None = None
    node_link_active: bool = False


CardDecision = NodeDisplayDecision


@dataclass(frozen=True)
class RevealMenuEntry:
    """Describe one reveal-menu entry for non-primary loader behavior."""

    alias: str
    node_name: str
    label: str
    checked: bool


__all__ = [
    "ActivationDefault",
    "ActivationSwitchRole",
    "ActivationSwitchSource",
    "CardBehavior",
    "CardBehaviorPatch",
    "CardDecision",
    "CardMode",
    "CollapseMode",
    "EnabledSwitchPolicy",
    "FieldBehavior",
    "FieldBehaviorPatch",
    "FieldPresentation",
    "LabelMode",
    "NodeBehaviorContext",
    "NodeBehaviorPatch",
    "NodeActivationOverride",
    "NodeActivationPolicy",
    "NodeDisplayDecision",
    "NodeVisibilityOverride",
    "OverrideBehavior",
    "OverrideBehaviorPatch",
    "OverridePinPolicy",
    "PackageBehaviorPatch",
    "PromptFieldBehavior",
    "PromptFieldBehaviorPatch",
    "PromptRole",
    "ResolvedNodeBehavior",
    "RevealMenuEntry",
    "RevealMode",
    "RowMode",
    "TitleControl",
    "VisibilityRule",
]
