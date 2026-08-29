"""Assembly of release notes into the changelog document.

The changelog document must contain an insert marker (a format comment, e.g.
``.. rtfc-insert`` for rst). The release notes of released versions are inserted
right after it.
"""

from __future__ import annotations

from rtfc._format import Format

__all__ = ("ChangelogError", "insert_version")


class ChangelogError(Exception):
    """Raised when the changelog document cannot be updated."""


def _with_trailing_newline(lines: list[str]) -> str:
    text = "\n".join(lines)
    return text if text.endswith("\n") else text + "\n"


def insert_version(changelog: str, notes: str, *, fmt: Format) -> str:
    """Insert the release notes of a version right after the insert marker.

    Args:
        changelog: The current changelog text.
        notes: The rendered release notes.
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
            inserted = [*lines[: index + 1], "", *notes.split("\n")]
            if rest:
                inserted += ["", *rest]
            return _with_trailing_newline(inserted)
    raise ChangelogError(f"Changelog is missing the {marker!r} insert marker")
