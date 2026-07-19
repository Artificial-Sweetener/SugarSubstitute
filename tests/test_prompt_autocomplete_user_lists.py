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

"""Behavior tests for custom and censored prompt autocomplete lists."""

from __future__ import annotations

from pathlib import Path

from substitute.application.managed_text_assets import (
    AutocompleteListManagedTextAssetService,
    CreateManagedTextAssetRequest,
    ManagedTextAssetKind,
)
from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.ports.prompt_tag_lexicon import PromptTagLexiconSnapshot
from substitute.application.prompt_autocomplete_lists import (
    PromptAutocompleteListKind,
    PromptAutocompleteListService,
)
from substitute.infrastructure.persistence.configured_prompt_autocomplete_gateway import (
    ConfiguredPromptAutocompleteGateway,
)
from substitute.infrastructure.persistence.file_prompt_autocomplete_list_repository import (
    FilePromptAutocompleteListRepository,
)


class _BundledCatalog:
    """Provide deterministic bundled suggestions and exact membership."""

    def __init__(self) -> None:
        self._suggestions = (
            PromptAutocompleteSuggestion(tag="rape", popularity=100),
            PromptAutocompleteSuggestion(tag="rapeseed", popularity=90),
            PromptAutocompleteSuggestion(tag="grape", popularity=80),
            PromptAutocompleteSuggestion(tag="radiant sky", popularity=70),
        )

    def search(
        self, prefix: str, limit: int = 10
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return prefix matches in fixed rank order."""

        normalized = prefix.casefold().replace("_", " ")
        return tuple(
            suggestion
            for suggestion in self._suggestions
            if suggestion.tag.casefold().startswith(normalized)
        )[:limit]

    def contains_prompt_tag(self, text: str) -> bool:
        """Return exact bundled membership."""

        normalized = text.casefold().replace("_", " ")
        return any(item.tag.casefold() == normalized for item in self._suggestions)

    def prepared_prompt_tag_snapshot(self) -> PromptTagLexiconSnapshot:
        """Return prepared bundled membership."""

        return PromptTagLexiconSnapshot(
            normalized_tags=frozenset(item.tag.casefold() for item in self._suggestions)
        )

    def load_prompt_tag_snapshot(self) -> PromptTagLexiconSnapshot:
        """Return loaded bundled membership."""

        return self.prepared_prompt_tag_snapshot()


def test_enabled_line_lists_add_custom_and_remove_only_exact_censored_tags(
    tmp_path: Path,
) -> None:
    """Enabled list lines should merge custom tags and censor exact identities."""

    list_service, gateway = _services(tmp_path)
    list_service.create_list(
        name="favorites",
        kind=PromptAutocompleteListKind.CUSTOM,
        text="radiant_armor\nradiant sky\n",
    )
    list_service.create_list(
        name="safety",
        kind=PromptAutocompleteListKind.CENSORED,
        text="rape\n",
    )

    assert [(item.tag, item.source_label) for item in gateway.search("ra", 10)] == [
        ("radiant armor", "custom"),
        ("radiant sky", "custom"),
        ("rapeseed", None),
    ]
    assert [item.tag for item in gateway.search("gr", 10)] == ["grape"]
    assert gateway.contains_prompt_tag("rape") is False
    assert gateway.contains_prompt_tag("radiant_armor") is True


def test_list_toggle_refreshes_behavior_immediately_without_rebuilding_gateway(
    tmp_path: Path,
) -> None:
    """A saved enablement change should alter the next query on the same gateway."""

    list_service, gateway = _services(tmp_path)
    censored = list_service.create_list(
        name="safety",
        kind=PromptAutocompleteListKind.CENSORED,
        text="rape\n",
    )
    revision_after_create = gateway.cache_revision

    assert [item.tag for item in gateway.search("ra")] == [
        "rapeseed",
        "radiant sky",
    ]

    list_service.set_enabled(censored.id, False)

    assert gateway.cache_revision > revision_after_create
    assert [item.tag for item in gateway.search("ra")] == [
        "rape",
        "rapeseed",
        "radiant sky",
    ]


def test_lists_are_portable_txt_files_with_separate_persisted_enablement(
    tmp_path: Path,
) -> None:
    """Tag content should live one-line-per-tag in user TXT namespaces."""

    list_service, _gateway = _services(tmp_path)
    custom = list_service.create_list(
        name="characters/cast",
        kind=PromptAutocompleteListKind.CUSTOM,
        text="alice\nbob, carol\n",
    )
    list_service.set_enabled(custom.id, False)

    text_path = tmp_path / "autocomplete" / "custom" / "characters" / "cast.txt"
    assert text_path.read_text(encoding="utf-8") == "alice\nbob, carol\n"
    assert list_service.list_lists()[0].enabled is False
    assert (tmp_path / "autocomplete" / "lists.json").is_file()


def test_managed_asset_adapter_keeps_custom_and_censored_lists_independent(
    tmp_path: Path,
) -> None:
    """The shared numbered modal adapter should create both named list kinds."""

    list_service, _gateway = _services(tmp_path)
    assets = AutocompleteListManagedTextAssetService(list_service)

    custom = assets.create_asset(
        CreateManagedTextAssetRequest(
            label="favorites",
            kind=ManagedTextAssetKind.PROMPT_TEXT,
            category="custom",
            content="blue hair\n",
        )
    )
    censored = assets.create_asset(
        CreateManagedTextAssetRequest(
            label="safety",
            kind=ManagedTextAssetKind.PROMPT_TEXT,
            category="censored",
            content="rape\n",
        )
    )

    assert custom.group == "Custom tag lists"
    assert censored.group == "Censored tag lists"
    assert custom.enabled is True
    assert assets.set_asset_enabled(custom.id, False).enabled is False


def _services(
    tmp_path: Path,
) -> tuple[PromptAutocompleteListService, ConfiguredPromptAutocompleteGateway]:
    """Build one file-backed list service and configured gateway."""

    service = PromptAutocompleteListService(
        FilePromptAutocompleteListRepository(tmp_path)
    )
    gateway = ConfiguredPromptAutocompleteGateway(_BundledCatalog(), service)
    service.set_change_callback(gateway.refresh)
    return service, gateway
