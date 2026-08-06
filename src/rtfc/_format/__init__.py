"""Documentation format abstraction.

A :class:`Format` produces the format-specific structure of the changelog
(headings, list items, comments); it never parses entry content. The rst
implementation is built in; third-party formats subclass :class:`Format` and
register under the ``rtfc.formats`` entry point group.
"""

from __future__ import annotations

import importlib.metadata

from rtfc._format.base import Format, FormatError
from rtfc._format.rst import RstFormat

__all__ = ("Format", "FormatError", "RstFormat", "get_format")

_ENTRY_POINT_GROUP = "rtfc.formats"

_BUILTIN_FORMATS: dict[str, type[Format]] = {RstFormat.name: RstFormat}


def get_format(name: str) -> Format:
    """Resolve a format by name.

    Built-in formats take priority; other names are looked up in the
    ``rtfc.formats`` entry point group.

    Raises:
        FormatError: If the name cannot be resolved to a :class:`Format`.
    """
    if name in _BUILTIN_FORMATS:
        return _BUILTIN_FORMATS[name]()
    for entry_point in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP, name=name):
        loaded = entry_point.load()
        if not (isinstance(loaded, type) and issubclass(loaded, Format)):
            raise FormatError(f"Entry point {name!r} in group {_ENTRY_POINT_GROUP!r} is not a Format subclass")
        return loaded()
    raise FormatError(f"Unknown format {name!r}")
