"""Base renderer definition."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from rtfc._config import Config
from rtfc._entry import Entry
from rtfc._format import Format

_METADATA_SORT_PREFIX = "metadata."


class RenderError(Exception):
    """Raised when entries cannot be rendered."""


@dataclass
class SectionGroup:
    """The entries of a changelog section, as exposed to version block templates."""

    id: str | None
    """Id of the section, or ``None`` for the unsectioned group."""

    label: str | None
    """Label of the section, or ``None`` for the unsectioned group."""

    entries: list[Entry]
    """The entries of the section, in file name order."""


def sort_entries(entries: Sequence[Entry], keys: Sequence[str]) -> list[Entry]:
    """Sort entries by the given keys: ``date``, ``nonce``, or ``metadata.<field>``.

    Entries missing a value sort last.

    Raises:
        RenderError: If a key is unknown or entry values cannot be compared.
    """
    for sort_key in keys:
        if sort_key not in ("date", "nonce") and not sort_key.startswith(_METADATA_SORT_PREFIX):
            raise RenderError(f"Unknown sort key {sort_key!r} (expected 'date', 'nonce' or 'metadata.<key>')")

    def key(entry: Entry) -> tuple[tuple[int, Any], ...]:
        parts: list[tuple[int, Any]] = []
        for sort_key in keys:
            if sort_key.startswith(_METADATA_SORT_PREFIX):
                # Metadata fields are top-level only, so the rest of the sort key is the literal field name:
                value = entry.metadata.get(sort_key.removeprefix(_METADATA_SORT_PREFIX))
            else:
                value = getattr(entry, sort_key)
            # Entries missing a value sort last, and (1, None) tuples compare equal:
            parts.append((1, None) if value is None else (0, value))
        return tuple(parts)

    try:
        return sorted(entries, key=key)
    except TypeError as exc:
        raise RenderError(f"Cannot sort entries by {list(keys)}: {exc}") from exc


class Renderer(ABC):
    """Renders changelog entries into version blocks."""

    def __init__(self, *, config: Config, fmt: Format) -> None:
        self.config = config
        self.fmt = fmt

    @abstractmethod
    def render_entry(self, entry: Entry) -> str:
        """Render a single entry into its changelog text, before list item wrapping.

        Raises:
            RenderError: If the entry cannot be rendered.
        """

    @abstractmethod
    def render_block(self, entries: Sequence[Entry], *, header: str) -> str:
        """Render entries into a version block, opened by the already-formatted ``header``.

        Raises:
            RenderError: If the entries cannot be rendered.
        """

    def group_entries(self, entries: Sequence[Entry]) -> list[SectionGroup]:
        """Group entries by section: the unsectioned group first, then the configured sections in order.

        Empty groups are included.
        """
        groups: dict[str | None, SectionGroup] = {None: SectionGroup(id=None, label=None, entries=[])}
        for section_id, section in self.config.sections.items():
            groups[section_id] = SectionGroup(id=section_id, label=section.label, entries=[])
        for entry in entries:
            groups[entry.section].entries.append(entry)
        return list(groups.values())
