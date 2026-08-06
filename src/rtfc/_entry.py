"""Changelog entry parsing and loading.

An entry file is made of a TOML frontmatter delimited by ``+++`` lines,
followed by the entry content::

    +++
    date = 2025-08-01
    nonce = "k3jf9a"
    section = "bugfix"

    [metadata]
    gh_issue = 123
    +++
    Fix a bug in the documentation format handling.

The content is treated as opaque text: it is never parsed, only incorporated
into the changelog where the documentation engine processes it.
"""

from __future__ import annotations

import datetime
import secrets
import tomllib
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

from rtfc._validation import (
    Field,
    Schema,
    ValidationContext,
    ValidationError,
    Validator,
    dict_of,
    iso_date,
    nullable,
    str_,
)

__all__ = ("ENTRY_SUFFIX", "Entry", "EntryError", "load_entries")

ENTRY_SUFFIX = ".rtfc"
"""File extension of changelog entry files."""


def _file_name(nonce: str, section: str | None) -> str:
    """The canonical entry file name: ``{nonce}.{section}.rtfc``, or ``{nonce}.rtfc`` without a section."""
    stem = nonce if section is None else f"{nonce}.{section}"
    return f"{stem}{ENTRY_SUFFIX}"


_DELIMITER = "+++"


class EntryError(Exception):
    """Raised when a changelog entry cannot be read or is invalid."""


class _FlatValue(Validator[Any]):
    """Accepts any value except tables: metadata fields are top-level only."""

    def validate(self, value: object, context: ValidationContext) -> Any:
        if isinstance(value, Mapping):
            raise ValidationError.single(context.path, "nested tables are not allowed")
        return value


class _Frontmatter(Schema):
    date = Field(iso_date)
    nonce = Field(str_)
    section = Field(nullable(str_), default=None)
    metadata = Field(dict_of(_FlatValue()), default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class Entry:
    """A changelog entry."""

    path: Path
    """The entry file."""

    date: datetime.date
    """Date of the change."""

    nonce: str
    """Unique identifier of the entry, part of the file name."""

    section: str | None
    """Id of the section the entry belongs to, if any."""

    metadata: dict[str, Any]
    """Free-form entry metadata."""

    content: str
    """Raw entry content, in the documentation format of the project."""

    @classmethod
    def create(
        cls,
        directory: Path,
        *,
        section: str | None = None,
        metadata: dict[str, Any] | None = None,
        content: str,
    ) -> Entry:
        """Create a new entry, dated today, with a generated nonce.

        The entry file is named after the nonce and section.

        Args:
            directory: The entry directory, from the configuration.
            section: Id of the section the entry belongs to, if any.
            metadata: Entry metadata.
            content: Entry content.
        """
        nonce = secrets.token_hex(4)
        return cls(
            path=directory / _file_name(nonce, section),
            date=datetime.date.today(),
            nonce=nonce,
            section=section,
            metadata=metadata or {},
            content=content,
        )

    @classmethod
    def from_file(
        cls, file: Path, *, sections: Collection[str], metadata_validator: Validator[dict[str, Any]] | None = None
    ) -> Entry:
        """Load an entry from ``file``.

        Args:
            file: The entry file to load.
            sections: Valid section ids, from the configuration.
            metadata_validator: Validator applied to the entry metadata, built
                from the configured metadata schema. ``None`` leaves metadata
                free-form.

        Raises:
            EntryError: If the entry cannot be read or is invalid.
        """
        try:
            text = file.read_text(encoding="utf-8")
        except OSError as exc:
            raise EntryError(f"{file.name}: {exc}") from exc
        try:
            data, body = _split_frontmatter(text)
            try:
                frontmatter = _Frontmatter.validate(data)
            except ValidationError as exc:
                raise EntryError(f"Invalid frontmatter:\n{exc}") from exc
            if frontmatter.section is not None and frontmatter.section not in sections:
                expected = ", ".join(map(repr, sections))
                raise EntryError(f"Unknown section {frontmatter.section!r} (expected one of: {expected})")
            metadata = frontmatter.metadata
            if metadata_validator is not None:
                try:
                    metadata = metadata_validator.validate(metadata, ValidationContext(path=("metadata",)))
                except ValidationError as exc:
                    raise EntryError(f"Invalid metadata:\n{exc}") from exc
            content = body.strip()
            if not content:
                raise EntryError("Entry has no content")
        except EntryError as exc:
            raise EntryError(f"{file.name}: {exc}") from exc
        expected_name = _file_name(frontmatter.nonce, frontmatter.section)
        if file.name != expected_name:
            raise EntryError(
                f"{file.name}: File name does not match the entry, expected {expected_name!r} "
                "(derived from the 'nonce' and 'section' fields)"
            )
        return cls(
            path=file,
            date=frontmatter.date,
            nonce=frontmatter.nonce,
            section=frontmatter.section,
            metadata=metadata,
            content=content,
        )

    def write(self) -> None:
        """Write the entry to its file, creating the entry directory if needed.

        Raises:
            EntryError: If a metadata value cannot be serialized to TOML.
        """
        frontmatter: dict[str, Any] = {"date": self.date, "nonce": self.nonce}
        if self.section is not None:
            frontmatter["section"] = self.section
        if self.metadata:
            frontmatter["metadata"] = self.metadata
        try:
            dumped = tomli_w.dumps(frontmatter)
        except TypeError as exc:
            raise EntryError(f"Cannot serialize frontmatter to TOML: {exc}") from exc
        text = f"{_DELIMITER}\n{dumped}{_DELIMITER}\n{self.content}\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split an entry file into its parsed TOML frontmatter and raw body."""
    lines = text.split("\n")
    if lines[0].rstrip() != _DELIMITER:
        raise EntryError(f"Entry must start with a {_DELIMITER!r} frontmatter delimiter")
    candidates = [i for i, line in enumerate(lines[1:], start=1) if line.rstrip() == _DELIMITER]
    if not candidates:
        raise EntryError(f"Missing closing {_DELIMITER!r} frontmatter delimiter")
    first_error: tomllib.TOMLDecodeError | None = None
    # The closing delimiter is the first `+++` line whose preceding text parses as valid
    # TOML. A bare `+++` line can only appear inside a TOML multiline string, in which
    # case the preceding text is invalid (unterminated string), so the first valid parse
    # is necessarily the true delimiter.
    for i in candidates:
        try:
            frontmatter = tomllib.loads("\n".join(lines[1:i]))
        except tomllib.TOMLDecodeError as exc:
            first_error = first_error or exc
            continue
        return frontmatter, "\n".join(lines[i + 1 :])
    raise EntryError(f"Invalid frontmatter TOML: {first_error}") from first_error


def load_entries(
    directory: Path, *, sections: Collection[str], metadata_validator: Validator[dict[str, Any]] | None = None
) -> list[Entry]:
    """Load all changelog entries from ``directory``.

    Only files with the ``.rtfc`` suffix are considered. Entries are returned
    in file name order; all invalid entries are reported together.

    Args:
        directory: The entry directory, from the configuration.
        sections: Valid section ids, from the configuration.
        metadata_validator: Validator applied to the entry metadata, built from
            the configured metadata schema. ``None`` leaves metadata free-form.

    Raises:
        EntryError: If the directory does not exist or any entry is invalid.
    """
    if not directory.is_dir():
        raise EntryError(f"Entry directory {str(directory)!r} does not exist")
    entries: list[Entry] = []
    errors: list[str] = []
    for file in sorted(directory.glob(f"*{ENTRY_SUFFIX}")):
        try:
            entries.append(Entry.from_file(file, sections=sections, metadata_validator=metadata_validator))
        except EntryError as exc:
            errors.append(str(exc))
    if errors:
        raise EntryError("\n".join(errors))
    return entries
