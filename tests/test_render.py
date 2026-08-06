import datetime
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from rtfc._config import Config, RenderConfig
from rtfc._entry import Entry
from rtfc._format import RstFormat
from rtfc._render import JinjaRenderer, Renderer, RenderError
from rtfc._render.base import sort_entries

RST = RstFormat()
HEADER = "v1.0.0 (2025-08-01)\n-------------------"

FLAT_TEMPLATE = """\
{{ header }}

{% for entry in entries | sort_entries %}
{{ list_item(render_entry(entry)) }}
{% endfor %}
"""


def make_entry(
    nonce: str,
    *,
    date: datetime.date = datetime.date(2025, 8, 1),
    section: str | None = None,
    metadata: dict[str, Any] | None = None,
    content: str = "Some change.",
) -> Entry:
    return Entry(
        path=Path(f"{nonce}.rtfc"),
        date=date,
        nonce=nonce,
        section=section,
        metadata=metadata or {},
        content=content,
    )


def make_config(**render: Any) -> Config:
    return Config.construct(changelog="changelog.rst", render=RenderConfig.construct(**render))


def render(entries: Sequence[Entry], **render_opts: Any) -> str:
    renderer = JinjaRenderer(config=make_config(**render_opts), fmt=RST)
    return renderer.render_block(entries, header=HEADER)


def test_render_block_sections_in_config_order() -> None:
    entries = [
        make_entry("a", section="bugfix", content="Fix a bug."),
        make_entry("b", section="feature", content="Add a feature."),
    ]

    assert render(entries) == (
        "v1.0.0 (2025-08-01)\n"
        "-------------------\n"
        "\n"
        "Features\n"
        "~~~~~~~~\n"
        "\n"
        "- Add a feature.\n"
        "\n"
        "Bug fixes\n"
        "~~~~~~~~~\n"
        "\n"
        "- Fix a bug."
    )


def test_render_block_empty_sections_omitted() -> None:
    entries = [make_entry("a", section="feature", content="Add a feature.")]

    assert "Bug fixes" not in render(entries)


def test_render_block_unsectioned_entries_first_unlabeled() -> None:
    entries = [
        make_entry("a", section="feature", content="Add a feature."),
        make_entry("b", content="General change."),
    ]

    assert render(entries) == (
        "v1.0.0 (2025-08-01)\n-------------------\n\n- General change.\n\nFeatures\n~~~~~~~~\n\n- Add a feature."
    )


def test_render_block_no_entries_renders_header_only() -> None:
    assert render([]) == HEADER


def test_render_block_multiline_content_indented() -> None:
    entries = [make_entry("a", content="Fix a bug\nspanning lines.")]

    assert render(entries).endswith("- Fix a bug\n  spanning lines.")


def test_render_block_default_sorts_by_date() -> None:
    entries = [
        make_entry("b", date=datetime.date(2025, 8, 2), content="Second."),
        make_entry("a", date=datetime.date(2025, 8, 1), content="First."),
    ]

    assert render(entries).endswith("- First.\n- Second.")


def test_custom_template_flat() -> None:
    entries = [
        make_entry("a", date=datetime.date(2025, 8, 2), section="bugfix", content="Fix a bug."),
        make_entry("b", date=datetime.date(2025, 8, 1), section="feature", content="Add a feature."),
    ]

    block = render(entries, template=FLAT_TEMPLATE)

    assert block == "v1.0.0 (2025-08-01)\n-------------------\n\n- Add a feature.\n- Fix a bug."


def test_custom_template_sort_filter_arguments() -> None:
    template = FLAT_TEMPLATE.replace("sort_entries", 'sort_entries("metadata.gh_issue")')
    entries = [
        make_entry("a", content="No issue."),
        make_entry("b", metadata={"gh_issue": 2}, content="Issue two."),
        make_entry("c", metadata={"gh_issue": 1}, content="Issue one."),
    ]

    block = render(entries, template=template)

    assert block.endswith("- Issue one.\n- Issue two.\n- No issue.")


def test_template_from_file(tmp_path: Path) -> None:
    (tmp_path / "t.jinja").write_text("{{ header }} ({{ entries | length }} changes)")
    renderer = JinjaRenderer(config=make_config(template_file=tmp_path / "t.jinja"), fmt=RST)

    block = renderer.render_block([make_entry("a")], header=HEADER)

    assert block == f"{HEADER} (1 changes)"


def test_render_block_entry_template_with_metadata() -> None:
    template = "{{ content }}{% if metadata.gh_issue %} (:gh:`{{ metadata.gh_issue }}`){% endif %}"
    entries = [
        make_entry("a", metadata={"gh_issue": 123}, content="Fix a bug."),
        make_entry("b", content="Another fix."),
    ]

    assert render(entries, entry_template=template).endswith("- Fix a bug. (:gh:`123`)\n- Another fix.")


def test_jinja_renderer_entry_template_from_file(tmp_path: Path) -> None:
    (tmp_path / "t.jinja").write_text("{{ content }} (templated)")
    renderer = JinjaRenderer(config=make_config(entry_template_file=tmp_path / "t.jinja"), fmt=RST)

    block = renderer.render_block([make_entry("a")], header=HEADER)

    assert block.endswith("- Some change. (templated)")


def test_custom_renderer_entry_hook() -> None:
    class UpperRenderer(JinjaRenderer):
        def render_entry(self, entry: Entry) -> str:
            return entry.content.upper()

    renderer = UpperRenderer(config=make_config(), fmt=RST)

    block = renderer.render_block([make_entry("a", content="Some change.")], header=HEADER)

    assert block.endswith("- SOME CHANGE.")


def test_custom_renderer_without_template_engine() -> None:
    class PlainRenderer(Renderer):
        def render_entry(self, entry: Entry) -> str:
            return entry.content

        def render_block(self, entries: Sequence[Entry], *, header: str) -> str:
            items = "\n".join(self.fmt.list_item(self.render_entry(entry)) for entry in entries)
            return f"{header}\n\n{items}"

    renderer = PlainRenderer(config=make_config(), fmt=RST)

    block = renderer.render_block([make_entry("a", content="Some change.")], header=HEADER)

    assert block == f"{HEADER}\n\n- Some change."


def test_sort_entries_multiple_keys() -> None:
    entries = [
        make_entry("b", date=datetime.date(2025, 8, 1)),
        make_entry("c", date=datetime.date(2025, 8, 1)),
        make_entry("a", date=datetime.date(2025, 8, 2)),
    ]

    assert [entry.nonce for entry in sort_entries(entries, ["date", "nonce"])] == ["b", "c", "a"]


def test_sort_entries_missing_metadata_last() -> None:
    entries = [
        make_entry("a"),
        make_entry("b", metadata={"gh_issue": 2}),
        make_entry("c", metadata={"gh_issue": 1}),
    ]

    assert [entry.nonce for entry in sort_entries(entries, ["metadata.gh_issue"])] == ["c", "b", "a"]


def test_sort_entries_dotted_metadata_key() -> None:
    entries = [
        make_entry("a", metadata={"gh.issue": 2}),
        make_entry("b", metadata={"gh.issue": 1}),
    ]

    assert [entry.nonce for entry in sort_entries(entries, ["metadata.gh.issue"])] == ["b", "a"]


def test_sort_entries_unknown_key() -> None:
    with pytest.raises(RenderError, match="Unknown sort key 'typo'"):
        sort_entries([make_entry("a")], ["typo"])


def test_sort_entries_incomparable_values() -> None:
    entries = [
        make_entry("a", metadata={"gh_issue": 1}),
        make_entry("b", metadata={"gh_issue": "2"}),
    ]

    with pytest.raises(RenderError, match=r"Cannot sort entries by \['metadata\.gh_issue'\]"):
        sort_entries(entries, ["metadata.gh_issue"])


def test_sort_error_propagates_from_template() -> None:
    template = FLAT_TEMPLATE.replace("sort_entries", 'sort_entries("typo")')

    with pytest.raises(RenderError, match="Unknown sort key 'typo'"):
        render([make_entry("a")], template=template)


def test_invalid_template_syntax() -> None:
    with pytest.raises(RenderError, match="Invalid template"):
        render([make_entry("a")], template="{% if %}")


def test_invalid_entry_template_syntax() -> None:
    with pytest.raises(RenderError, match="Invalid entry template"):
        render([make_entry("a")], entry_template="{% if %}")


def test_entry_template_runtime_error() -> None:
    with pytest.raises(RenderError, match=r"a\.rtfc: Failed to render entry"):
        render([make_entry("a")], entry_template="{{ content() }}")


def test_template_runtime_error() -> None:
    with pytest.raises(RenderError, match="Failed to render version block"):
        render([make_entry("a")], template="{{ header() }}")
