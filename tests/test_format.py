import datetime

import pytest

from rtfc._format import Format, FormatError, RstFormat, get_format

RST = RstFormat()


def test_rst_heading_levels() -> None:
    assert RST.heading("Title", 1) == "Title\n-----"
    assert RST.heading("Title", 2) == "Title\n~~~~~"


def test_rst_comment() -> None:
    assert RST.comment("rtfc-insert") == ".. rtfc-insert"


def test_version_header() -> None:
    assert RST.version_header("1.3.0", datetime.date(2025, 8, 1)) == "v1.3.0 (2025-08-01)\n-------------------"


def test_unreleased_header() -> None:
    assert RST.unreleased_header() == "Unreleased\n----------"


def test_section_header() -> None:
    assert RST.section_header("Bug fixes") == "Bug fixes\n~~~~~~~~~"


def test_list_item_single_line() -> None:
    assert RST.list_item("Fix a bug.") == "- Fix a bug."


def test_list_item_multiline_indents_continuation() -> None:
    assert RST.list_item("Fix a bug\nspanning lines.") == "- Fix a bug\n  spanning lines."


def test_list_item_blank_lines_not_indented() -> None:
    assert RST.list_item("Fix a bug.\n\nWith details.") == "- Fix a bug.\n\n  With details."


def test_insert_marker() -> None:
    assert RST.insert_marker() == ".. rtfc-insert"


def test_incomplete_format_cannot_be_instantiated() -> None:
    class Incomplete(Format):
        name = "incomplete"

        def comment(self, text: str) -> str:
            return text

    with pytest.raises(TypeError, match="abstract"):
        Incomplete()  # pyright: ignore[reportAbstractUsage]


def test_get_format_builtin() -> None:
    assert isinstance(get_format("rst"), RstFormat)


def test_get_format_unknown() -> None:
    with pytest.raises(FormatError, match="Unknown format 'typo'"):
        get_format("typo")
