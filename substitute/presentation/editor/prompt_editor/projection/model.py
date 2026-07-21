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

"""Define the run-based prompt projection types used by the rich editor surface."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from substitute.application.prompt_editor.prompt_lora_resolution_service import (
    PromptLoraResolutionStatus,
)


_OBJECT_REPLACEMENT_CHARACTER = "\ufffc"
_STANDARD_THUMBNAIL_ROLE = "standard"


class PromptProjectionCaretStopSequence(Protocol):
    """Describe caret-stop sequences with optimized position membership."""

    def has_projection_position(self, projection_position: int) -> bool:
        """Return whether the sequence contains one projection boundary."""
        ...

    def projection_position_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return the projection boundary for a state when cheaply available."""
        ...

    def state_for_projection_position(
        self,
        projection_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return the state for a projection boundary when cheaply available."""
        ...

    def state_for_source_position(
        self,
        source_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState | None:
        """Return the state for a source boundary when cheaply available."""
        ...

    def resolve_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Resolve a state against the sequence when cheaply available."""
        ...


class PromptProjectionDisplayMode(str, Enum):
    """Enumerate the supported prompt editor display modes."""

    RAW = "raw"
    PROJECTED = "projected"


class PromptProjectionRunKind(str, Enum):
    """Enumerate the visible run kinds emitted by the projection builder."""

    TEXT = "text"
    INLINE_OBJECT = "inline_object"


class PromptProjectionRunRole(str, Enum):
    """Enumerate special token-decoration roles assigned to projection runs."""

    DEFAULT = "default"
    TOKEN_LEADING_DECORATION = "token_leading_decoration"
    TOKEN_TRAILING_DECORATION = "token_trailing_decoration"


class PromptProjectionTokenKind(str, Enum):
    """Enumerate the prompt syntax token kinds supported by the projection."""

    EMPHASIS = "emphasis"
    LORA = "lora"
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


class PromptProjectionCaretPlacement(str, Enum):
    """Enumerate the logical caret slot owned by one projection state."""

    PLAIN_TEXT = "plain_text"
    TOKEN_LEADING_EDGE = "token_leading_edge"
    TOKEN_CONTENT = "token_content"
    TOKEN_TRAILING_EDGE = "token_trailing_edge"


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
    status_text: str | None = None
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


@dataclass(frozen=True, slots=True)
class PromptProjectionRun:
    """Describe one visible inline run emitted by the projection builder."""

    run_id: str
    kind: PromptProjectionRunKind
    source_start: int
    source_end: int
    display_text: str
    source_positions: Sequence[int]
    projection_start: int
    projection_end: int
    token_id: str | None = None
    renderer_key: str | None = None
    role: PromptProjectionRunRole = PromptProjectionRunRole.DEFAULT
    active: bool = False
    source_backed: bool = True
    ghosted: bool = False
    text_style_variant: str | None = None

    def __post_init__(self) -> None:
        """Validate the run invariants required by the unified layout path."""

        if self.kind is PromptProjectionRunKind.TEXT:
            expected_boundary_count = len(self.display_text) + 1
            if len(self.source_positions) != expected_boundary_count:
                raise ValueError(
                    "Text runs must expose one source boundary for each visible "
                    f"character plus one trailing boundary. Got "
                    f"{len(self.source_positions)} boundaries for "
                    f"{len(self.display_text)} visible characters."
                )
            if self.projection_end - self.projection_start != len(self.display_text):
                raise ValueError(
                    "Text run projection ranges must match the visible text length."
                )
        else:
            if len(self.source_positions) < 2:
                raise ValueError(
                    "Inline object runs must expose at least leading and trailing "
                    "source boundaries."
                )
            if self.projection_end - self.projection_start != 1:
                raise ValueError(
                    "Inline object runs must occupy exactly one projection slot."
                )
            if self.renderer_key is None:
                raise ValueError(
                    "Inline object runs must declare the renderer key that owns them."
                )

    @property
    def is_text(self) -> bool:
        """Return whether this run contributes visible text characters."""

        return self.kind is PromptProjectionRunKind.TEXT

    @property
    def is_inline_object(self) -> bool:
        """Return whether this run contributes one inline object slot."""

        return self.kind is PromptProjectionRunKind.INLINE_OBJECT


@dataclass(frozen=True, slots=True)
class PromptProjectionCaretPosition:
    """Describe one source-backed caret position in the projection surface."""

    source_position: int


@dataclass(frozen=True, slots=True)
class PromptProjectionCaretState:
    """Describe one logical caret slot inside the projected prompt document."""

    source_position: int
    placement: PromptProjectionCaretPlacement = (
        PromptProjectionCaretPlacement.PLAIN_TEXT
    )
    token_id: str | None = None
    run_id: str | None = None
    token_slot: int | None = None

    @property
    def is_token_state(self) -> bool:
        """Return whether this caret state belongs to a semantic token."""

        return self.token_id is not None


@dataclass(frozen=True, slots=True)
class PromptProjectionCaretStop:
    """Describe one ordered visual caret stop inside the projection document."""

    visual_index: int
    projection_position: int
    state: PromptProjectionCaretState


@dataclass(frozen=True, slots=True)
class PromptProjectionSelection:
    """Describe one source-backed selection in the projection surface."""

    anchor_position: int
    cursor_position: int

    @property
    def start(self) -> int:
        """Return the inclusive selection start."""

        return min(self.anchor_position, self.cursor_position)

    @property
    def end(self) -> int:
        """Return the exclusive selection end."""

        return max(self.anchor_position, self.cursor_position)

    @property
    def is_empty(self) -> bool:
        """Return whether the selection currently covers no source text."""

        return self.anchor_position == self.cursor_position


@dataclass(frozen=True, slots=True)
class PromptProjectionCaretMap:
    """Track ordered visual caret stops across the full projection document."""

    stops: Sequence[PromptProjectionCaretStop]
    tokens: Sequence[PromptProjectionToken]
    source_length: int
    projection_length: int
    _index_by_state: dict[PromptProjectionCaretState, int] | None = field(
        init=False,
        repr=False,
        compare=False,
    )
    _states_by_source_position: (
        dict[
            int,
            tuple[PromptProjectionCaretState, ...],
        ]
        | None
    ) = field(
        init=False,
        repr=False,
        compare=False,
    )
    _states_by_projection_position: (
        dict[
            int,
            tuple[PromptProjectionCaretState, ...],
        ]
        | None
    ) = field(
        init=False,
        repr=False,
        compare=False,
    )
    _projection_positions: frozenset[int] | None = field(
        init=False,
        repr=False,
        compare=False,
    )
    _first_state_by_source_position: dict[int, PromptProjectionCaretState] | None = (
        field(
            init=False,
            repr=False,
            compare=False,
        )
    )
    _last_state_by_source_position: dict[int, PromptProjectionCaretState] | None = (
        field(
            init=False,
            repr=False,
            compare=False,
        )
    )
    _first_state_by_projection_position: (
        dict[int, PromptProjectionCaretState] | None
    ) = field(
        init=False,
        repr=False,
        compare=False,
    )
    _last_state_by_projection_position: dict[int, PromptProjectionCaretState] | None = (
        field(
            init=False,
            repr=False,
            compare=False,
        )
    )
    _projection_position_by_state: dict[PromptProjectionCaretState, int] | None = field(
        init=False,
        repr=False,
        compare=False,
    )
    _tokens_by_id: dict[str, PromptProjectionToken] | None = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """Index caret stops and tokens for fast cursor-state lookups."""

        object.__setattr__(self, "_index_by_state", None)
        object.__setattr__(self, "_states_by_source_position", None)
        object.__setattr__(self, "_states_by_projection_position", None)
        object.__setattr__(self, "_first_state_by_source_position", None)
        object.__setattr__(self, "_last_state_by_source_position", None)
        object.__setattr__(self, "_first_state_by_projection_position", None)
        object.__setattr__(self, "_last_state_by_projection_position", None)
        object.__setattr__(self, "_projection_positions", None)
        object.__setattr__(self, "_projection_position_by_state", None)
        object.__setattr__(self, "_tokens_by_id", None)

    def token_by_id(self, token_id: str | None) -> PromptProjectionToken | None:
        """Return the token owning one caret state when it still exists."""

        if token_id is None:
            return None
        optimized_lookup = getattr(self.tokens, "token_by_id", None)
        if callable(optimized_lookup):
            token = optimized_lookup(token_id)
            return token if isinstance(token, PromptProjectionToken) else None
        tokens_by_id = self._tokens_by_id
        if tokens_by_id is None:
            tokens_by_id = {token.token_id: token for token in self.tokens}
            object.__setattr__(self, "_tokens_by_id", tokens_by_id)
        return tokens_by_id.get(token_id)

    def projection_position_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int:
        """Return the projection boundary position for one caret state."""

        resolved_state = self.resolve_state(state)
        optimized_projection_position = self._optimized_projection_position_for_state(
            resolved_state
        )
        if optimized_projection_position is not None:
            return optimized_projection_position
        return self._projection_position_by_state_index()[resolved_state]

    def has_projection_position(self, projection_position: int) -> bool:
        """Return whether one exact projection boundary owns a real caret state."""

        optimized_stops = self.stops
        has_projection_position = getattr(
            optimized_stops,
            "has_projection_position",
            None,
        )
        if callable(has_projection_position):
            return bool(has_projection_position(projection_position))
        return projection_position in self._projection_positions_index()

    def state_for_projection_position(
        self,
        projection_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState:
        """Return the best visual caret state for one projection boundary."""

        if not self.stops:
            return PromptProjectionCaretState(source_position=0)
        clamped_position = max(0, min(projection_position, self.projection_length))
        optimized_state = self._optimized_state_for_projection_position(
            clamped_position,
            prefer_after=prefer_after,
        )
        if optimized_state is not None:
            return optimized_state
        matching_state = (
            self._last_state_by_projection_position_index().get(clamped_position)
            if prefer_after
            else self._first_state_by_projection_position_index().get(clamped_position)
        )
        if matching_state is not None:
            return matching_state

        states_by_projection_position = self._projection_position_states()
        matching_states = states_by_projection_position.get(clamped_position)
        if matching_states:
            return matching_states[-1] if prefer_after else matching_states[0]

        nearest_before = max(
            (
                position
                for position in states_by_projection_position
                if position <= clamped_position
            ),
            default=None,
        )
        nearest_after = min(
            (
                position
                for position in states_by_projection_position
                if position >= clamped_position
            ),
            default=None,
        )
        if prefer_after and nearest_after is not None:
            return states_by_projection_position[nearest_after][0]
        if nearest_before is not None:
            return states_by_projection_position[nearest_before][-1]
        assert nearest_after is not None
        return states_by_projection_position[nearest_after][0]

    def next_state(
        self,
        current_state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState:
        """Return the next visual caret state after the supplied state."""

        if not self.stops:
            return current_state
        optimized_state = self._optimized_adjacent_state(
            current_state,
            method_name="next_state",
        )
        if optimized_state is not None:
            return optimized_state
        resolved_state = self.resolve_state(current_state)
        current_index = self._index_by_state_index()[resolved_state]
        if current_index >= len(self.stops) - 1:
            return self.stops[-1].state
        return self.stops[current_index + 1].state

    def previous_state(
        self,
        current_state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState:
        """Return the previous visual caret state before the supplied state."""

        if not self.stops:
            return current_state
        optimized_state = self._optimized_adjacent_state(
            current_state,
            method_name="previous_state",
        )
        if optimized_state is not None:
            return optimized_state
        resolved_state = self.resolve_state(current_state)
        current_index = self._index_by_state_index()[resolved_state]
        if current_index <= 0:
            return self.stops[0].state
        return self.stops[current_index - 1].state

    def state_for_source_position(
        self,
        source_position: int,
        *,
        prefer_after: bool = False,
    ) -> PromptProjectionCaretState:
        """Return the best visual caret state for one raw source boundary."""

        if not self.stops:
            return PromptProjectionCaretState(
                source_position=max(0, min(source_position, self.source_length))
            )
        clamped_position = max(0, min(source_position, self.source_length))
        optimized_state = self._optimized_state_for_source_position(
            clamped_position,
            prefer_after=prefer_after,
        )
        if optimized_state is not None:
            return optimized_state
        if callable(getattr(self.stops, "state_for_source_position", None)):
            token = self.token_covering_source_position(clamped_position)
            if token is not None:
                return self._state_inside_token(
                    token,
                    source_position=clamped_position,
                    prefer_after=prefer_after,
                )
        matching_state = (
            self._last_state_by_source_position_index().get(clamped_position)
            if prefer_after
            else self._first_state_by_source_position_index().get(clamped_position)
        )
        if matching_state is not None:
            return matching_state

        states_by_source_position = self._source_position_states()
        matching_states = states_by_source_position.get(clamped_position)
        if matching_states:
            return matching_states[-1] if prefer_after else matching_states[0]

        token = self.token_covering_source_position(clamped_position)
        if token is not None:
            return self._state_inside_token(
                token,
                source_position=clamped_position,
                prefer_after=prefer_after,
            )

        nearest_before = max(
            (
                position
                for position in states_by_source_position
                if position <= clamped_position
            ),
            default=None,
        )
        nearest_after = min(
            (
                position
                for position in states_by_source_position
                if position >= clamped_position
            ),
            default=None,
        )
        if prefer_after and nearest_after is not None:
            return states_by_source_position[nearest_after][0]
        if nearest_before is not None:
            return states_by_source_position[nearest_before][-1]
        assert nearest_after is not None
        return states_by_source_position[nearest_after][0]

    def resolve_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState:
        """Resolve one possibly stale caret state against the current stop list."""

        if not self.stops:
            return state
        optimized_state = self._optimized_resolve_state(state)
        if optimized_state is not None:
            return optimized_state
        if callable(getattr(self.stops, "resolve_state", None)):
            token = self.token_by_id(state.token_id)
            if token is not None:
                try:
                    return self._state_inside_token(
                        token,
                        source_position=state.source_position,
                        prefer_after=state.placement
                        is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
                        token_slot=state.token_slot,
                        placement=state.placement,
                    )
                except AssertionError:
                    pass
            return self.state_for_source_position(
                state.source_position,
                prefer_after=state.placement
                is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
            )
        direct_match = self._index_by_state_index().get(state)
        if direct_match is not None:
            return self.stops[direct_match].state

        token = self.token_by_id(state.token_id)
        if token is not None:
            try:
                return self._state_inside_token(
                    token,
                    source_position=state.source_position,
                    prefer_after=state.placement
                    is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
                    token_slot=state.token_slot,
                    placement=state.placement,
                )
            except AssertionError:
                pass

        return self.state_for_source_position(
            state.source_position,
            prefer_after=state.placement
            is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
        )

    def token_covering_source_position(
        self,
        source_position: int,
    ) -> PromptProjectionToken | None:
        """Return the semantic token covering one raw source position when present."""

        for token in self.tokens:
            if token.source_start <= source_position < token.source_end:
                return token
        return None

    def token_starting_at_source_position(
        self,
        source_position: int,
    ) -> PromptProjectionToken | None:
        """Return the token whose outer range begins at the supplied source position."""

        return next(
            (token for token in self.tokens if token.source_start == source_position),
            None,
        )

    def token_ending_at_source_position(
        self,
        source_position: int,
    ) -> PromptProjectionToken | None:
        """Return the token whose outer range ends at the supplied source position."""

        return next(
            (token for token in self.tokens if token.source_end == source_position),
            None,
        )

    def _optimized_projection_position_for_state(
        self,
        state: PromptProjectionCaretState,
    ) -> int | None:
        """Return an optimized state projection lookup when stops provide one."""

        projection_position_for_state = getattr(
            self.stops,
            "projection_position_for_state",
            None,
        )
        if not callable(projection_position_for_state):
            return None
        projection_position = projection_position_for_state(state)
        return int(projection_position) if projection_position is not None else None

    def _optimized_state_for_projection_position(
        self,
        projection_position: int,
        *,
        prefer_after: bool,
    ) -> PromptProjectionCaretState | None:
        """Return an optimized projection-position state lookup when available."""

        state_for_projection_position = getattr(
            self.stops,
            "state_for_projection_position",
            None,
        )
        if not callable(state_for_projection_position):
            return None
        state = state_for_projection_position(
            projection_position,
            prefer_after=prefer_after,
        )
        return state if isinstance(state, PromptProjectionCaretState) else None

    def _optimized_state_for_source_position(
        self,
        source_position: int,
        *,
        prefer_after: bool,
    ) -> PromptProjectionCaretState | None:
        """Return an optimized source-position state lookup when available."""

        state_for_source_position = getattr(
            self.stops,
            "state_for_source_position",
            None,
        )
        if not callable(state_for_source_position):
            return None
        state = state_for_source_position(source_position, prefer_after=prefer_after)
        return state if isinstance(state, PromptProjectionCaretState) else None

    def _optimized_resolve_state(
        self,
        state: PromptProjectionCaretState,
    ) -> PromptProjectionCaretState | None:
        """Return an optimized resolved state when stops provide one."""

        resolve_state = getattr(self.stops, "resolve_state", None)
        if not callable(resolve_state):
            return None
        resolved_state = resolve_state(state)
        return (
            resolved_state
            if isinstance(resolved_state, PromptProjectionCaretState)
            else None
        )

    def _optimized_adjacent_state(
        self,
        state: PromptProjectionCaretState,
        *,
        method_name: str,
    ) -> PromptProjectionCaretState | None:
        """Return adjacent visual state when the stop sequence can avoid indexing."""

        adjacent_state = getattr(self.stops, method_name, None)
        if not callable(adjacent_state):
            return None
        resolved_state = adjacent_state(state)
        return (
            resolved_state
            if isinstance(resolved_state, PromptProjectionCaretState)
            else None
        )

    def _index_by_state_index(self) -> dict[PromptProjectionCaretState, int]:
        """Return caret-state visual indexes, building them only when needed."""

        index_by_state = self._index_by_state
        if index_by_state is None:
            index_by_state = {stop.state: stop.visual_index for stop in self.stops}
            object.__setattr__(self, "_index_by_state", index_by_state)
        return index_by_state

    def _first_state_by_source_position_index(
        self,
    ) -> dict[int, PromptProjectionCaretState]:
        """Return first visual states by source position, building on demand."""

        first_state_by_source_position = self._first_state_by_source_position
        if first_state_by_source_position is None:
            first_state_by_source_position = {}
            for stop in self.stops:
                first_state_by_source_position.setdefault(
                    stop.state.source_position,
                    stop.state,
                )
            object.__setattr__(
                self,
                "_first_state_by_source_position",
                first_state_by_source_position,
            )
        return first_state_by_source_position

    def _last_state_by_source_position_index(
        self,
    ) -> dict[int, PromptProjectionCaretState]:
        """Return last visual states by source position, building on demand."""

        last_state_by_source_position = self._last_state_by_source_position
        if last_state_by_source_position is None:
            last_state_by_source_position = {
                stop.state.source_position: stop.state for stop in self.stops
            }
            object.__setattr__(
                self,
                "_last_state_by_source_position",
                last_state_by_source_position,
            )
        return last_state_by_source_position

    def _first_state_by_projection_position_index(
        self,
    ) -> dict[int, PromptProjectionCaretState]:
        """Return first visual states by projection position, building on demand."""

        first_state_by_projection_position = self._first_state_by_projection_position
        if first_state_by_projection_position is None:
            first_state_by_projection_position = {}
            for stop in self.stops:
                first_state_by_projection_position.setdefault(
                    stop.projection_position,
                    stop.state,
                )
            object.__setattr__(
                self,
                "_first_state_by_projection_position",
                first_state_by_projection_position,
            )
        return first_state_by_projection_position

    def _last_state_by_projection_position_index(
        self,
    ) -> dict[int, PromptProjectionCaretState]:
        """Return last visual states by projection position, building on demand."""

        last_state_by_projection_position = self._last_state_by_projection_position
        if last_state_by_projection_position is None:
            last_state_by_projection_position = {
                stop.projection_position: stop.state for stop in self.stops
            }
            object.__setattr__(
                self,
                "_last_state_by_projection_position",
                last_state_by_projection_position,
            )
        return last_state_by_projection_position

    def _projection_positions_index(self) -> frozenset[int]:
        """Return available projection positions, building them only when needed."""

        projection_positions = self._projection_positions
        if projection_positions is None:
            projection_positions = frozenset(
                stop.projection_position for stop in self.stops
            )
            object.__setattr__(self, "_projection_positions", projection_positions)
        return projection_positions

    def _projection_position_by_state_index(
        self,
    ) -> dict[PromptProjectionCaretState, int]:
        """Return projection positions by state, building only when needed."""

        projection_position_by_state = self._projection_position_by_state
        if projection_position_by_state is None:
            projection_position_by_state = {
                stop.state: stop.projection_position for stop in self.stops
            }
            object.__setattr__(
                self,
                "_projection_position_by_state",
                projection_position_by_state,
            )
        return projection_position_by_state

    def _source_position_states(
        self,
    ) -> dict[int, tuple[PromptProjectionCaretState, ...]]:
        """Return source-position states, building the index only on demand."""

        states_by_source_position = self._states_by_source_position
        if states_by_source_position is None:
            states_by_source_position = self._build_states_by_source_position()
            object.__setattr__(
                self,
                "_states_by_source_position",
                states_by_source_position,
            )
        return states_by_source_position

    def _projection_position_states(
        self,
    ) -> dict[int, tuple[PromptProjectionCaretState, ...]]:
        """Return projection-position states, building the index only on demand."""

        states_by_projection_position = self._states_by_projection_position
        if states_by_projection_position is None:
            states_by_projection_position = self._build_states_by_projection_position()
            object.__setattr__(
                self,
                "_states_by_projection_position",
                states_by_projection_position,
            )
        return states_by_projection_position

    def _build_states_by_source_position(
        self,
    ) -> dict[int, tuple[PromptProjectionCaretState, ...]]:
        """Group caret states by raw source position in visual order."""

        states_by_source_position: dict[int, list[PromptProjectionCaretState]] = {}
        for stop in self.stops:
            states_by_source_position.setdefault(stop.state.source_position, []).append(
                stop.state
            )
        return {
            position: tuple(states)
            for position, states in states_by_source_position.items()
        }

    def _build_states_by_projection_position(
        self,
    ) -> dict[int, tuple[PromptProjectionCaretState, ...]]:
        """Group caret states by projection boundary position in visual order."""

        states_by_projection_position: dict[int, list[PromptProjectionCaretState]] = {}
        for stop in self.stops:
            states_by_projection_position.setdefault(
                stop.projection_position, []
            ).append(stop.state)
        return {
            position: tuple(states)
            for position, states in states_by_projection_position.items()
        }

    def _state_inside_token(
        self,
        token: PromptProjectionToken,
        *,
        source_position: int,
        prefer_after: bool,
        token_slot: int | None = None,
        placement: PromptProjectionCaretPlacement | None = None,
    ) -> PromptProjectionCaretState:
        """Resolve one token-backed raw position into the appropriate caret state."""

        if token.navigation_mode is PromptProjectionTokenNavigationMode.ATOMIC:
            desired_placement = (
                PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
                if prefer_after
                or source_position >= token.source_end
                or placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
                else PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
            )
            return self._first_matching_state(
                token=token,
                placement=desired_placement,
                token_slot=None,
            )

        assert token.content_start is not None
        assert token.content_end is not None

        if placement is PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE:
            return self._first_matching_state(
                token=token,
                placement=PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE,
                token_slot=None,
            )
        if placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE:
            return self._first_matching_state(
                token=token,
                placement=PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
                token_slot=None,
            )
        if (
            placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
            and token_slot is not None
        ):
            return self._first_matching_state(
                token=token,
                placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
                token_slot=max(
                    0, min(token_slot, token.content_end - token.content_start)
                ),
            )

        if source_position <= token.source_start:
            return self._first_matching_state(
                token=token,
                placement=PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE,
                token_slot=None,
            )
        if source_position >= token.source_end:
            return self._first_matching_state(
                token=token,
                placement=PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
                token_slot=None,
            )
        if source_position < token.content_start:
            return self._first_matching_state(
                token=token,
                placement=(
                    PromptProjectionCaretPlacement.TOKEN_CONTENT
                    if prefer_after
                    else PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
                ),
                token_slot=0 if prefer_after else None,
            )
        if source_position > token.content_end:
            return self._first_matching_state(
                token=token,
                placement=(
                    PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
                    if prefer_after
                    else PromptProjectionCaretPlacement.TOKEN_CONTENT
                ),
                token_slot=(
                    None if prefer_after else token.content_end - token.content_start
                ),
            )
        return self._first_matching_state(
            token=token,
            placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
            token_slot=source_position - token.content_start,
        )

    def _first_matching_state(
        self,
        *,
        token: PromptProjectionToken,
        placement: PromptProjectionCaretPlacement,
        token_slot: int | None,
    ) -> PromptProjectionCaretState:
        """Return the first matching caret state already stored for one token."""

        matching_token_state = getattr(self.stops, "matching_token_state", None)
        if callable(matching_token_state):
            optimized_state = matching_token_state(
                token.token_id,
                placement=placement,
                token_slot=token_slot,
            )
            if isinstance(optimized_state, PromptProjectionCaretState):
                return optimized_state
        for stop in self.stops:
            state = stop.state
            if state.token_id != token.token_id:
                continue
            if state.placement is not placement:
                continue
            if state.token_slot != token_slot:
                continue
            return state
        raise AssertionError(
            "Missing caret state for token "
            f"{token.token_id!r}, placement={placement!s}, token_slot={token_slot!r}."
        )


@dataclass(frozen=True, slots=True)
class PromptProjectionMapping:
    """Map raw source indices onto the ordered projection run stream."""

    runs: Sequence[PromptProjectionRun]
    source_length: int
    projection_length: int
    _runs_by_id: dict[str, PromptProjectionRun] | None = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """Index runs for efficient lookup."""

        object.__setattr__(self, "_runs_by_id", None)

    def run_by_id(self, run_id: str | None) -> PromptProjectionRun | None:
        """Return the run with the supplied identifier when it exists."""

        if run_id is None:
            return None
        optimized_lookup = getattr(self.runs, "run_by_id", None)
        if callable(optimized_lookup):
            run = optimized_lookup(run_id)
            return run if isinstance(run, PromptProjectionRun) else None
        runs_by_id = self._runs_by_id
        if runs_by_id is None:
            runs_by_id = {run.run_id: run for run in self.runs}
            object.__setattr__(self, "_runs_by_id", runs_by_id)
        return runs_by_id.get(run_id)

    def runs_for_token(
        self,
        token_id: str,
    ) -> tuple[PromptProjectionRun, ...]:
        """Return the visible runs owned by one semantic token."""

        return tuple(run for run in self.runs if run.token_id == token_id)

    def run_at_projection_position(
        self,
        projection_position: int,
        *,
        prefer_previous: bool = False,
    ) -> PromptProjectionRun | None:
        """Return the run adjacent to one projection boundary."""

        clamped_position = max(0, min(projection_position, self.projection_length))
        optimized_lookup = getattr(self.runs, "run_at_projection_position", None)
        if callable(optimized_lookup):
            run = optimized_lookup(
                clamped_position,
                prefer_previous=prefer_previous,
            )
            return run if isinstance(run, PromptProjectionRun) else None
        if prefer_previous:
            for run in reversed(self.runs):
                if run.projection_start < clamped_position <= run.projection_end:
                    return run
        for run in self.runs:
            if run.projection_start <= clamped_position < run.projection_end:
                return run
        return None

    def text_projection_ranges_for_source_range(
        self,
        start: int,
        end: int,
    ) -> tuple[tuple[int, int], ...]:
        """Return text-only projection ranges covering one raw source range."""

        selection_start = max(0, min(start, end))
        selection_end = min(self.source_length, max(start, end))
        if selection_end <= selection_start:
            return ()

        ranges: list[tuple[int, int]] = []
        for run in self.runs:
            if not run.is_text or not run.source_backed:
                continue
            run_source_start = run.source_positions[0]
            run_source_end = run.source_positions[-1]
            overlap_start = max(selection_start, run_source_start)
            overlap_end = min(selection_end, run_source_end)
            if overlap_end <= overlap_start:
                continue
            start_index = run.source_positions.index(overlap_start)
            end_index = run.source_positions.index(overlap_end)
            ranges.append(
                (
                    run.projection_start + start_index,
                    run.projection_start + end_index,
                )
            )

        if not ranges:
            return ()

        merged_ranges: list[tuple[int, int]] = []
        current_start, current_end = ranges[0]
        for next_start, next_end in ranges[1:]:
            if next_start == current_end:
                current_end = next_end
                continue
            merged_ranges.append((current_start, current_end))
            current_start, current_end = next_start, next_end
        merged_ranges.append((current_start, current_end))
        return tuple(merged_ranges)


@dataclass(frozen=True, slots=True)
class PromptProjectionDocument:
    """Describe one full run-based prompt projection plus its lookup mapping."""

    display_mode: PromptProjectionDisplayMode
    source_text: str
    projection_text: str
    runs: Sequence[PromptProjectionRun]
    tokens: Sequence[PromptProjectionToken]
    mapping: PromptProjectionMapping
    caret_map: PromptProjectionCaretMap
    _tokens_by_id: dict[str, PromptProjectionToken] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    def token_by_id(self, token_id: str | None) -> PromptProjectionToken | None:
        """Return the semantic token matching one stable token identifier."""

        if token_id is None:
            return None
        optimized_lookup = getattr(self.tokens, "token_by_id", None)
        if callable(optimized_lookup):
            token = optimized_lookup(token_id)
            return token if isinstance(token, PromptProjectionToken) else None
        tokens_by_id = self._tokens_by_id
        if tokens_by_id is None:
            tokens_by_id = {token.token_id: token for token in self.tokens}
            object.__setattr__(self, "_tokens_by_id", tokens_by_id)
        return tokens_by_id.get(token_id)

    def run_by_id(self, run_id: str | None) -> PromptProjectionRun | None:
        """Return the visible run matching one stable run identifier."""

        return self.mapping.run_by_id(run_id)

    def runs_for_token(
        self,
        token_id: str,
    ) -> tuple[PromptProjectionRun, ...]:
        """Return the visible runs owned by one semantic token."""

        return self.mapping.runs_for_token(token_id)


@dataclass(frozen=True, slots=True)
class PromptProjectionInlinePreview:
    """Describe visible inline projection text that is not committed source."""

    source_position: int
    suffix_text: str


@dataclass(frozen=True, slots=True)
class PromptProjectionTransientState:
    """Collect transient projection adornments applied to the active document."""

    autocomplete_preview: PromptProjectionInlinePreview | None = None


OBJECT_REPLACEMENT_CHARACTER = _OBJECT_REPLACEMENT_CHARACTER

__all__ = [
    "OBJECT_REPLACEMENT_CHARACTER",
    "PromptProjectionCaretMap",
    "PromptProjectionCaretPlacement",
    "PromptProjectionCaretPosition",
    "PromptProjectionCaretState",
    "PromptProjectionCaretStop",
    "PromptProjectionDisplayMode",
    "PromptProjectionDocument",
    "PromptProjectionInlinePreview",
    "PromptProjectionMapping",
    "PromptProjectionRun",
    "PromptProjectionRunKind",
    "PromptProjectionRunRole",
    "PromptProjectionSelection",
    "PromptProjectionTransientState",
    "PromptProjectionThumbnailVariant",
    "PromptProjectionToken",
    "PromptProjectionTokenKind",
    "PromptProjectionTokenNavigationMode",
]
