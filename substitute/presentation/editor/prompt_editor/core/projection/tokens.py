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

"""Define immutable semantic token values consumed by prompt projection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sugarsubstitute_shared.localization import ApplicationText

from substitute.application.prompt_editor.lora.resolution import (
    PromptLoraResolutionStatus,
)

_STANDARD_THUMBNAIL_ROLE = "standard"


class PromptProjectionTokenKind(str, Enum):
    """Enumerate the prompt syntax token kinds supported by the projection."""

    EMPHASIS = "emphasis"
    LORA = "lora"
    REGION_SEPARATOR = "region_separator"
    SCENE = "scene"
    WILDCARD = "wildcard"


class PromptProjectionTokenNavigationMode(str, Enum):
    """Enumerate how one semantic token participates in caret navigation."""

    ATOMIC = "atomic"
    TEXT_CONTENT = "text_content"


type PromptWeightControlIdentity = tuple[
    str,
    PromptProjectionTokenKind,
    int,
    int,
]


@dataclass(frozen=True, slots=True)
class PromptProjectionThumbnailVariant:
    """Reference one prepared thumbnail asset available to projection renderers."""

    size: int
    storage_key: str
    width: int
    height: int
    content_format: str
    byte_size: int
    role: str = _STANDARD_THUMBNAIL_ROLE


@dataclass(frozen=True, slots=True)
class PromptProjectionToken:
    """Describe one semantic syntax token rendered inside the projection."""

    token_id: str
    kind: PromptProjectionTokenKind
    source_start: int
    source_end: int
    display_text: str
    value_text: str | None = None
    status_text: ApplicationText | None = None
    style_variant: str | None = None
    wildcard_display_tag: str | None = None
    wildcard_tag_is_explicit: bool = False
    wildcard_tag_is_numeric: bool = False
    wildcard_can_step_tag: bool = False
    detail_text: str | None = None
    lora_status: PromptLoraResolutionStatus | None = None
    lora_status_reason: str | None = None
    lora_match_source: str | None = None
    lora_authority: bool = False
    lora_backend_value: str | None = None
    lora_version_text: str | None = None
    lora_trained_words: tuple[str, ...] = ()
    model_page_url: str | None = None
    thumbnail_variants: tuple[PromptProjectionThumbnailVariant, ...] = ()
    exists: bool = True
    active: bool = False
    decoration_accented: bool = False
    synthetic: bool = False
    content_start: int | None = None
    content_end: int | None = None
    editing_value_text: str | None = None
    editing_slot_width: float | None = None
    editing_caret_index: int | None = None
    editing_select_all: bool = False
    navigation_mode: PromptProjectionTokenNavigationMode = (
        PromptProjectionTokenNavigationMode.ATOMIC
    )

    @property
    def content_range(self) -> tuple[int, int] | None:
        """Return the visible content range when this token supports it."""

        if self.content_start is None or self.content_end is None:
            return None
        return (self.content_start, self.content_end)

    @property
    def supports_text_content_navigation(self) -> bool:
        """Return whether the token exposes internal visible-text caret stops."""

        return (
            self.navigation_mode is PromptProjectionTokenNavigationMode.TEXT_CONTENT
            and self.content_start is not None
            and self.content_end is not None
        )


def prompt_weight_content_identity(
    *,
    kind: PromptProjectionTokenKind,
    content_start: int,
    content_end: int,
) -> PromptWeightControlIdentity:
    """Return the stable identity for one visible prompt weight content span."""

    return ("prompt-weight-content", kind, content_start, content_end)


def prompt_weight_control_identity(
    token: PromptProjectionToken,
) -> PromptWeightControlIdentity:
    """Return the default wheel identity for one prompt weight control token."""

    content_range = token.content_range
    if content_range is not None:
        return prompt_weight_content_identity(
            kind=token.kind,
            content_start=content_range[0],
            content_end=content_range[1],
        )
    return ("prompt-weight-source", token.kind, token.source_start, token.source_end)
