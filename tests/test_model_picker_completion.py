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

"""Contract tests for model picker inline-completion matching."""

from __future__ import annotations

from substitute.presentation.widgets.inline_completion import InlineCompletion
from substitute.presentation.widgets.model_picker.model_picker_completion import (
    model_picker_inline_completion,
)
from substitute.presentation.widgets.model_picker.model_picker_models import (
    ModelPickerItem,
)


def test_model_picker_completion_uses_filename_without_extension() -> None:
    """Plain queries should complete against the model filename."""

    completion = model_picker_inline_completion(
        query="aman",
        item=_item(relative_path="Illustrious/amanatsuIllustrious_v11.safetensors"),
    )

    assert completion == InlineCompletion(
        channel="filename",
        completed_text="amanatsuIllustrious_v11",
        suffix_text="atsuIllustrious_v11",
    )


def test_model_picker_completion_uses_filename_substring_matches() -> None:
    """Filename search substrings should complete against the matching tail."""

    completion = model_picker_inline_completion(
        query="Friendly",
        item=_item(
            relative_path="Illustrious/notFriendlyName_v11.safetensors",
            title="Completely Different",
        ),
    )

    assert completion == InlineCompletion(
        channel="filename",
        completed_text="FriendlyName_v11",
        suffix_text="Name_v11",
    )


def test_model_picker_completion_strips_supported_extensions() -> None:
    """Filename candidates should strip every supported model extension."""

    assert model_picker_inline_completion(
        query="model",
        item=_item(relative_path="folder/model.ckpt"),
    ) == InlineCompletion(
        channel="filename",
        completed_text="model",
        suffix_text="",
    )
    assert model_picker_inline_completion(
        query="model",
        item=_item(relative_path="folder/model.pt"),
    ) == InlineCompletion(
        channel="filename",
        completed_text="model",
        suffix_text="",
    )


def test_model_picker_completion_path_channel_requires_separator() -> None:
    """Path completions should only be selected for path-shaped queries."""

    completion = model_picker_inline_completion(
        query="Illustrious/aman",
        item=_item(relative_path="Illustrious/amanatsuIllustrious_v11.safetensors"),
    )

    assert completion == InlineCompletion(
        channel="path",
        completed_text="Illustrious/amanatsuIllustrious_v11",
        suffix_text="atsuIllustrious_v11",
    )

    plain_completion = model_picker_inline_completion(
        query="aman",
        item=_item(relative_path="Illustrious/amanatsuIllustrious_v11.safetensors"),
    )

    assert plain_completion is not None
    assert plain_completion.channel == "filename"


def test_model_picker_completion_path_treats_separators_as_equivalent() -> None:
    """Path matching should tolerate either Windows or POSIX separators."""

    completion = model_picker_inline_completion(
        query=r"Illustrious\aman",
        item=_item(relative_path="Illustrious/amanatsuIllustrious_v11.safetensors"),
    )

    assert completion == InlineCompletion(
        channel="path",
        completed_text=r"Illustrious\amanatsuIllustrious_v11",
        suffix_text="atsuIllustrious_v11",
    )


def test_model_picker_completion_path_preserves_typed_separator_style() -> None:
    """Path completions should continue with the separator style the user typed."""

    slash_completion = model_picker_inline_completion(
        query="Illustrious/aman",
        item=_item(relative_path=r"Illustrious\amanatsuIllustrious_v11.safetensors"),
    )
    backslash_completion = model_picker_inline_completion(
        query=r"Illustrious\aman",
        item=_item(relative_path="Illustrious/amanatsuIllustrious_v11.safetensors"),
    )

    assert slash_completion is not None
    assert slash_completion.completed_text == "Illustrious/amanatsuIllustrious_v11"
    assert backslash_completion is not None
    assert backslash_completion.completed_text == r"Illustrious\amanatsuIllustrious_v11"


def test_model_picker_completion_uses_friendly_name() -> None:
    """Friendly display names should be a fallback completion channel."""

    completion = model_picker_inline_completion(
        query="T-noob",
        item=_item(
            relative_path="Illustrious/tNoobnai3_v9.safetensors",
            title="T-noobnai3",
        ),
    )

    assert completion == InlineCompletion(
        channel="friendly_name",
        completed_text="T-noobnai3",
        suffix_text="nai3",
    )


def test_model_picker_completion_includes_friendly_subtitle() -> None:
    """Friendly completion should use the same title-subtitle label as closed display."""

    completion = model_picker_inline_completion(
        query="T-noob",
        item=_item(
            relative_path="Illustrious/tNoobnai3_v9.safetensors",
            title="T-noobnai3",
            subtitle="v9",
        ),
    )

    assert completion == InlineCompletion(
        channel="friendly_name",
        completed_text="T-noobnai3 - v9",
        suffix_text="nai3 - v9",
    )


def test_model_picker_completion_rejects_friendly_substring_matches() -> None:
    """Filtering may use substrings, but ghost text should not."""

    assert (
        model_picker_inline_completion(
            query="v9",
            item=_item(
                relative_path="Illustrious/tNoobnai3_v9.safetensors",
                title="T-noobnai3",
                subtitle="v9",
            ),
        )
        is None
    )


def test_model_picker_completion_prefers_path_when_query_contains_separator() -> None:
    """Path-shaped queries should prefer path completion over filename/friendly names."""

    completion = model_picker_inline_completion(
        query="Folder/Alpha",
        item=_item(
            relative_path="Folder/AlphaModel.safetensors",
            title="Folder/Alpha Friendly",
        ),
    )

    assert completion is not None
    assert completion.channel == "path"
    assert completion.completed_text == "Folder/AlphaModel"


def test_model_picker_completion_prefers_filename_for_plain_query() -> None:
    """Plain queries should prefer filenames before friendly names."""

    completion = model_picker_inline_completion(
        query="Alpha",
        item=_item(
            relative_path="Folder/AlphaModel.safetensors",
            title="Alpha Friendly",
        ),
    )

    assert completion is not None
    assert completion.channel == "filename"
    assert completion.completed_text == "AlphaModel"


def test_model_picker_completion_returns_none_without_item() -> None:
    """No current picker item means no ghost completion."""

    assert model_picker_inline_completion(query="Alpha", item=None) is None


def _item(
    *,
    relative_path: str,
    title: str = "Model Title",
    subtitle: str | None = None,
) -> ModelPickerItem:
    """Return one picker item for completion tests."""

    return ModelPickerItem(
        item_id=relative_path,
        title=title,
        subtitle=subtitle,
        backend_value=relative_path,
        relative_path=relative_path,
        folder=relative_path.rsplit("/", 1)[0] if "/" in relative_path else "",
        search_text=f"{title} {relative_path}".casefold(),
        thumbnail_variants=(),
        aspect_ratio=1.0,
        model_page_url=None,
        payload=relative_path,
    )
