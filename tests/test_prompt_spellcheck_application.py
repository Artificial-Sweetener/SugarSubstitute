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

"""Contract tests for prompt-aware spellcheck application services."""

from __future__ import annotations

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptSpellcheckCandidateService,
    PromptSpellcheckService,
)
from substitute.infrastructure.persistence.file_prompt_autocomplete_gateway import (
    FilePromptAutocompleteGateway,
)


class _FakeTagLexicon:
    """Record exact tag lookups for candidate filtering tests."""

    def __init__(self, tags: set[str]) -> None:
        """Store normalized exact tags."""

        self._tags = {
            " ".join(tag.replace("_", " ").casefold().split()) for tag in tags
        }
        self.lookups: list[str] = []

    def contains_prompt_tag(self, text: str) -> bool:
        """Return exact membership without prefix behavior."""

        self.lookups.append(text)
        normalized = " ".join(text.replace("_", " ").casefold().split())
        return normalized in self._tags

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Fail if spellcheck tries to use prefix autocomplete for correctness."""

        _ = prefix
        _ = limit
        raise AssertionError("Spellcheck must use exact tag lexicon membership.")


class _FakeSpellCheckGateway:
    """Provide deterministic backend behavior for spellcheck service tests."""

    def __init__(
        self,
        *,
        rejected_words: set[str] | None = None,
        available: bool = True,
    ) -> None:
        """Store rejected words and call recording."""

        self._rejected_words = rejected_words or set()
        self._available = available
        self.checked_words: list[str] = []
        self.suggested_words: list[str] = []
        self.ignored_words: list[str] = []
        self.added_words: list[str] = []

    def is_available(self) -> bool:
        """Return configured availability."""

        return self._available

    def availability_reason(self) -> str | None:
        """Return a deterministic unavailable reason."""

        return None if self._available else "missing dictionary"

    def check_word(self, word: str) -> bool:
        """Reject configured words."""

        self.checked_words.append(word)
        return word.casefold() not in self._rejected_words

    def suggest(self, word: str, *, limit: int = 8) -> tuple[str, ...]:
        """Return deterministic suggestions."""

        self.suggested_words.append(word)
        return tuple(f"{word}{index}" for index in range(limit + 1))

    def supports_session_ignore(self) -> bool:
        """Return that session ignore is supported."""

        return True

    def ignore_for_session(self, word: str) -> None:
        """Record session ignored words."""

        self.ignored_words.append(word)

    def supports_persistent_add(self) -> bool:
        """Return that persistent add is supported."""

        return True

    def add_to_dictionary(self, word: str) -> bool:
        """Record persistent additions."""

        self.added_words.append(word)
        return True


def test_candidate_service_extracts_prose_and_skips_prompt_syntax() -> None:
    """Candidate extraction should prefer prose and suppress prompt syntax."""

    service = PromptSpellcheckCandidateService(tag_lexicon=_FakeTagLexicon(set()))

    candidates = service.candidates_for_text(
        "A beutiful landscap, <lora:ModelName:0.8>, {wild/card}, (cat:1.2)"
    )

    assert tuple(candidate.text for candidate in candidates) == (
        "A",
        "beutiful",
        "landscap",
    )


def test_candidate_service_skips_machine_like_tokens() -> None:
    """Paths, URLs, hashes, numbers, underscores, and model-like names are skipped."""

    service = PromptSpellcheckCandidateService(tag_lexicon=_FakeTagLexicon(set()))

    candidates = service.candidates_for_text(
        "https://example.test/cat, C:\\models\\foo.safetensors, "
        "abc_def, 123cat, 0xabcdef12, SDXLModel"
    )

    assert candidates == ()


def test_candidate_service_uses_exact_tag_lexicon_not_prefix_search() -> None:
    """Autocomplete-known suppression must use exact tag membership."""

    lexicon = _FakeTagLexicon({"looking at viewer"})
    service = PromptSpellcheckCandidateService(tag_lexicon=lexicon)

    candidates = service.candidates_for_text("looking at viewer, lovly prose")

    assert tuple(candidate.text for candidate in candidates) == ("lovly", "prose")
    assert "looking at viewer" in lexicon.lookups


def test_file_prompt_autocomplete_gateway_supports_exact_tag_lookup() -> None:
    """The bundled autocomplete gateway should also answer exact tag membership."""

    gateway = FilePromptAutocompleteGateway()

    assert gateway.contains_prompt_tag("looking_at_viewer") is True
    assert gateway.contains_prompt_tag("looking at viewer") is True
    assert gateway.contains_prompt_tag("looking at view") is False


def test_spellcheck_snapshot_checks_each_word_once_without_suggestions() -> None:
    """Snapshot generation should dedupe checks and avoid suggestion lookup."""

    gateway = _FakeSpellCheckGateway(rejected_words={"typo"})
    service = PromptSpellcheckService(
        gateway=gateway,
        candidate_service=PromptSpellcheckCandidateService(
            tag_lexicon=_FakeTagLexicon(set())
        ),
    )

    snapshot = service.snapshot_for_text("typo typo")

    assert tuple(
        (issue.source_start, issue.source_end) for issue in snapshot.issues
    ) == (
        (0, 4),
        (5, 9),
    )
    assert gateway.checked_words == ["typo"]
    assert gateway.suggested_words == []


def test_spellcheck_suggestions_are_lazy_and_cached() -> None:
    """Suggestions should be fetched only for context-menu use and then cached."""

    gateway = _FakeSpellCheckGateway(rejected_words={"typo"})
    service = PromptSpellcheckService(
        gateway=gateway,
        candidate_service=PromptSpellcheckCandidateService(
            tag_lexicon=_FakeTagLexicon(set())
        ),
    )

    first = service.suggestions_for_word("typo")
    second = service.suggestions_for_word("typo")

    assert first.suggestions == second.suggestions
    assert first.suggestions == tuple(f"typo{index}" for index in range(8))
    assert gateway.suggested_words == ["typo"]


def test_spellcheck_session_ignore_suppresses_future_issues() -> None:
    """Session ignored words should not appear in later snapshots."""

    gateway = _FakeSpellCheckGateway(rejected_words={"typo"})
    service = PromptSpellcheckService(
        gateway=gateway,
        candidate_service=PromptSpellcheckCandidateService(
            tag_lexicon=_FakeTagLexicon(set())
        ),
    )

    service.ignore_word_for_session("typo")
    snapshot = service.snapshot_for_text("typo")

    assert snapshot.issues == ()
    assert gateway.ignored_words == ["typo"]


def test_spellcheck_unavailable_gateway_returns_empty_snapshot() -> None:
    """Unavailable backends should not create prompt diagnostics."""

    gateway = _FakeSpellCheckGateway(available=False)
    service = PromptSpellcheckService(
        gateway=gateway,
        candidate_service=PromptSpellcheckCandidateService(
            tag_lexicon=_FakeTagLexicon(set())
        ),
    )

    snapshot = service.snapshot_for_text("typo")

    assert snapshot.issues == ()
    assert snapshot.unavailable_reason == "missing dictionary"
