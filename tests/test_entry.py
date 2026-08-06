import datetime
from pathlib import Path

import pytest

from rtfc._entry import Entry, EntryError, load_entries
from rtfc._validation import Field, int_, record, str_

SECTIONS = ("feature", "bugfix")


def write_entry(directory: Path, name: str, text: str) -> Path:
    file = directory / name
    file.write_text(text, encoding="utf-8")
    return file


def test_load_entry(tmp_path: Path) -> None:
    file = write_entry(
        tmp_path,
        "k3jf9a.bugfix.rtfc",
        """+++
date = 2025-08-01
nonce = "k3jf9a"
section = "bugfix"

[metadata]
gh_issue = 123
is_backport = true
+++
Fix a bug where :meth:`~pydantic.BaseModel.model_dump` would crash on
recursive references.
""",
    )

    entry = Entry.from_file(file, sections=SECTIONS)

    assert entry == Entry(
        path=file,
        date=datetime.date(2025, 8, 1),
        nonce="k3jf9a",
        section="bugfix",
        metadata={"gh_issue": 123, "is_backport": True},
        content=("Fix a bug where :meth:`~pydantic.BaseModel.model_dump` would crash on\nrecursive references."),
    )


def test_load_entry_defaults(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", '+++\ndate = 2025-08-01\nnonce = "abc"\n+++\nSome change.')

    entry = Entry.from_file(file, sections=SECTIONS)

    assert entry.section is None
    assert entry.metadata == {}


def test_load_entry_date_as_iso_string(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", '+++\ndate = "2025-08-01"\nnonce = "abc"\n+++\nSome change.')

    assert Entry.from_file(file, sections=SECTIONS).date == datetime.date(2025, 8, 1)


def test_load_entry_delimiter_inside_multiline_string(tmp_path: Path) -> None:
    file = write_entry(
        tmp_path,
        "abc.rtfc",
        '+++\ndate = 2025-08-01\nnonce = "abc"\n[metadata]\nnote = """\n+++\n"""\n+++\nSome change.',
    )

    entry = Entry.from_file(file, sections=SECTIONS)

    assert entry.metadata == {"note": "+++\n"}
    assert entry.content == "Some change."


def test_load_entry_content_stripped_but_raw(tmp_path: Path) -> None:
    file = write_entry(
        tmp_path,
        "abc.rtfc",
        '+++\ndate = 2025-08-01\nnonce = "abc"\n+++\n\nA list:\n\n- item one\n- item +++ two\n\n',
    )

    assert Entry.from_file(file, sections=SECTIONS).content == "A list:\n\n- item one\n- item +++ two"


def test_load_entry_missing_opening_delimiter(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", 'date = 2025-08-01\nnonce = "abc"\n+++\nSome change.')

    with pytest.raises(EntryError, match=r"abc\.rtfc: Entry must start with a '\+\+\+' frontmatter delimiter"):
        Entry.from_file(file, sections=SECTIONS)


def test_load_entry_missing_closing_delimiter(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", '+++\ndate = 2025-08-01\nnonce = "abc"\nSome change.')

    with pytest.raises(EntryError, match=r"abc\.rtfc: Missing closing '\+\+\+' frontmatter delimiter"):
        Entry.from_file(file, sections=SECTIONS)


def test_load_entry_invalid_toml(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", "+++\ndate =\n+++\nSome change.")

    with pytest.raises(EntryError, match=r"abc\.rtfc: Invalid frontmatter TOML"):
        Entry.from_file(file, sections=SECTIONS)


def test_load_entry_invalid_frontmatter(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", "+++\ndate = 2025-08-01\nsection = 1\ntypo = true\n+++\nSome change.")

    with pytest.raises(EntryError) as exc_info:
        Entry.from_file(file, sections=SECTIONS)

    message = str(exc_info.value)
    assert "abc.rtfc: Invalid frontmatter:" in message
    assert "nonce: missing required key" in message
    assert "section: expected str, got int" in message
    assert "typo: unknown key" in message


def test_load_entry_unknown_section(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", '+++\ndate = 2025-08-01\nnonce = "abc"\nsection = "typo"\n+++\nChange.')

    with pytest.raises(EntryError, match=r"abc\.rtfc: Unknown section 'typo' \(expected one of: 'feature', 'bugfix'\)"):
        Entry.from_file(file, sections=SECTIONS)


def test_load_entry_empty_content(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", '+++\ndate = 2025-08-01\nnonce = "abc"\n+++\n\n')

    with pytest.raises(EntryError, match=r"abc\.rtfc: Entry has no content"):
        Entry.from_file(file, sections=SECTIONS)


def test_load_entry_nonce_file_name_mismatch(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", '+++\ndate = 2025-08-01\nnonce = "other"\n+++\nSome change.')

    with pytest.raises(EntryError, match=r"abc\.rtfc: File name does not match the entry, expected 'other\.rtfc'"):
        Entry.from_file(file, sections=SECTIONS)


def test_load_entry_section_missing_from_file_name(tmp_path: Path) -> None:
    file = write_entry(tmp_path, "abc.rtfc", '+++\ndate = 2025-08-01\nnonce = "abc"\nsection = "bugfix"\n+++\nFix.')

    with pytest.raises(
        EntryError, match=r"abc\.rtfc: File name does not match the entry, expected 'abc\.bugfix\.rtfc'"
    ):
        Entry.from_file(file, sections=SECTIONS)


def test_load_entries(tmp_path: Path) -> None:
    write_entry(tmp_path, "b.rtfc", '+++\ndate = 2025-08-02\nnonce = "b"\n+++\nSecond.')
    write_entry(tmp_path, "a.rtfc", '+++\ndate = 2025-08-01\nnonce = "a"\n+++\nFirst.')
    write_entry(tmp_path, "notes.txt", "not an entry")

    entries = load_entries(tmp_path, sections=SECTIONS)

    assert [entry.nonce for entry in entries] == ["a", "b"]


def test_load_entries_empty_directory(tmp_path: Path) -> None:
    assert load_entries(tmp_path, sections=SECTIONS) == []


def test_load_entries_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(EntryError, match="does not exist"):
        load_entries(tmp_path / "missing", sections=SECTIONS)


def test_load_entries_collects_all_errors(tmp_path: Path) -> None:
    write_entry(tmp_path, "a.rtfc", '+++\ndate = 2025-08-01\nnonce = "a"\n+++\nValid.')
    write_entry(tmp_path, "b.rtfc", "no frontmatter")
    write_entry(tmp_path, "c.rtfc", '+++\ndate = 2025-08-01\nnonce = "c"\n+++\n')

    with pytest.raises(EntryError) as exc_info:
        load_entries(tmp_path, sections=SECTIONS)

    message = str(exc_info.value)
    assert "b.rtfc: Entry must start with" in message
    assert "c.rtfc: Entry has no content" in message


METADATA = record({"gh_issue": Field(int_), "author": Field(str_, default="unknown")})


def test_load_entry_metadata_schema(tmp_path: Path) -> None:
    file = write_entry(
        tmp_path, "abc.rtfc", '+++\ndate = 2025-08-01\nnonce = "abc"\n[metadata]\ngh_issue = 123\n+++\nChange.'
    )

    entry = Entry.from_file(file, sections=SECTIONS, metadata_validator=METADATA)

    assert entry.metadata == {"gh_issue": 123, "author": "unknown"}


def test_load_entry_metadata_schema_invalid(tmp_path: Path) -> None:
    file = write_entry(
        tmp_path,
        "abc.rtfc",
        '+++\ndate = 2025-08-01\nnonce = "abc"\n[metadata]\ngh_issue = "x"\ntypo = 1\n+++\nChange.',
    )

    with pytest.raises(EntryError) as exc_info:
        Entry.from_file(file, sections=SECTIONS, metadata_validator=METADATA)

    message = str(exc_info.value)
    assert "abc.rtfc: Invalid metadata:" in message
    assert "metadata.gh_issue: expected int, got str" in message
    assert "metadata.typo: unknown key" in message


def test_load_entry_nested_metadata_rejected(tmp_path: Path) -> None:
    file = write_entry(
        tmp_path, "abc.rtfc", '+++\ndate = 2025-08-01\nnonce = "abc"\n[metadata.gh]\nissue = 1\n+++\nChange.'
    )

    with pytest.raises(EntryError) as exc_info:
        Entry.from_file(file, sections=SECTIONS)

    assert "metadata.gh: nested tables are not allowed" in str(exc_info.value)


def test_create_and_write_roundtrip(tmp_path: Path) -> None:
    created = Entry.create(
        tmp_path / "changelog",
        section="bugfix",
        metadata={
            "gh_issue": 123,
            "backport": True,
            "score": 1.5,
            "author": 'quote "me"',
            "since": datetime.date(2025, 8, 1),
        },
        content="Fix a bug.",
    )
    created.write()

    loaded = Entry.from_file(created.path, sections=SECTIONS)

    assert loaded == created
    assert created.date == datetime.date.today()
    assert created.path.name == f"{created.nonce}.bugfix.rtfc"


def test_create_defaults(tmp_path: Path) -> None:
    entry = Entry.create(tmp_path, content="Change.")

    assert entry.section is None
    assert entry.metadata == {}


def test_write_unserializable_metadata(tmp_path: Path) -> None:
    entry = Entry.create(tmp_path, metadata={"bad": object()}, content="Change.")

    with pytest.raises(EntryError, match="Cannot serialize frontmatter to TOML"):
        entry.write()
