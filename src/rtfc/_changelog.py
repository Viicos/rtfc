"""Assembly of version blocks into the changelog document.

The changelog document must contain an insert marker (a format comment, e.g.
``.. rtfc-insert`` for rst): released version blocks are inserted right after
it, newest first.
"""

from __future__ import annotations

from rtfc._format import Format

__all__ = ("ChangelogError", "insert_version")


class ChangelogError(Exception):
    """Raised when the changelog document cannot be updated."""


def _with_trailing_newline(lines: list[str]) -> str:
    text = "\n".join(lines)
    return text if text.endswith("\n") else text + "\n"


def insert_version(changelog: str, block: str, *, fmt: Format) -> str:
    """Insert a released version block right after the insert marker.

    Args:
        changelog: The current changelog text.
        block: The rendered version block.
        fmt: The documentation format.

    Raises:
        ChangelogError: If the insert marker is missing.
    """
    lines = changelog.split("\n")
    marker = fmt.insert_marker()
    for index, line in enumerate(lines):
        if line.strip() == marker:
            rest = lines[index + 1 :]
            while rest and not rest[0].strip():
                rest.pop(0)
            inserted = [*lines[: index + 1], "", *block.split("\n")]
            if rest:
                inserted += ["", *rest]
            return _with_trailing_newline(inserted)
    raise ChangelogError(f"Changelog is missing the {marker!r} insert marker")
