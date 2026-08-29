"""The reStructuredText documentation format."""

from __future__ import annotations

from typing import ClassVar

from rtfc._format.base import Format


class RstFormat(Format):
    """The reStructuredText format, for sphinx documentation."""

    name: ClassVar[str] = "rst"

    # Assumes the changelog document title is underlined with '=':
    _underlines: ClassVar[dict[int, str]] = {1: "-", 2: "~"}

    def heading(self, title: str, level: int) -> str:
        return f"{title}\n{self._underlines[level] * len(title)}"

    def comment(self, text: str) -> str:
        return f".. {text}"

    def list_item(self, text: str) -> str:
        first, *rest = text.splitlines()
        lines = [f"- {first}", *(f"  {line}" if line else "" for line in rest)]
        return "\n".join(lines)
