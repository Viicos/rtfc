"""Base documentation format definition."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from typing import ClassVar, final

# The marker identity is format-independent (only the comment syntax around it
# varies), so the changelog assembly logic can locate it in any format:
_INSERT_MARKER = "rtfc-insert"


class FormatError(Exception):
    """Raised when a documentation format cannot be resolved."""


class Format(ABC):
    """A documentation format, defining the structure of the changelog."""

    name: ClassVar[str]
    """Name of the format, as referenced by the ``format`` configuration value."""

    @abstractmethod
    def heading(self, title: str, level: int) -> str:
        """Format a heading.

        Args:
            title: The heading title.
            level: Heading level, relative to the changelog document title:
                ``1`` for versions, ``2`` for sections.
        """

    @abstractmethod
    def comment(self, text: str) -> str:
        """Format ``text`` as a comment, invisible in the rendered document."""

    def version_header(self, version: str, date: datetime.date) -> str:
        """Format the heading of a released version."""
        return self.heading(f"v{version} ({date.isoformat()})", 1)

    def unreleased_header(self) -> str:
        """Format the heading of the unreleased changes."""
        return self.heading("Unreleased", 1)

    def section_header(self, label: str) -> str:
        """Format the heading of an entry section."""
        return self.heading(label, 2)

    def list_item(self, text: str) -> str:
        """Format already-rendered entry text as a list item."""
        first, *rest = text.splitlines()
        lines = [f"- {first}", *(f"  {line}" if line else "" for line in rest)]
        return "\n".join(lines)

    @final
    def insert_marker(self) -> str:
        """The comment after which new version blocks are inserted."""
        return self.comment(_INSERT_MARKER)
