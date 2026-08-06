"""The Jinja template based renderer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import jinja2

from rtfc._config import Config
from rtfc._entry import Entry
from rtfc._format import Format
from rtfc._render.base import Renderer, RenderError, sort_entries

_env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
_env.filters["sort_entries"] = lambda entries, *keys: sort_entries(entries, keys or ("date",))


class JinjaRenderer(Renderer):
    """The default renderer, driven by the configured Jinja templates.

    The version block template receives ``header``, ``entries`` (all entries),
    ``sections`` (the :class:`~rtfc._render.base.SectionGroup` of each
    section), the ``render_entry()``, ``list_item()`` and ``section_header()``
    functions, and can sort entries with the ``sort_entries()`` filter. The
    entry template receives ``content``, ``date``, ``nonce``, ``section`` and
    ``metadata``.
    """

    def __init__(self, *, config: Config, fmt: Format) -> None:
        """
        Args:
            config: The project configuration.
            fmt: The documentation format.

        Raises:
            RenderError: If a template is invalid.
            ConfigError: If a template file cannot be read.
        """
        super().__init__(config=config, fmt=fmt)
        try:
            self._template = _env.from_string(config.render.resolve_template())
        except jinja2.TemplateSyntaxError as exc:
            raise RenderError(f"Invalid template: {exc}") from exc
        try:
            self._entry_template = _env.from_string(config.render.resolve_entry_template())
        except jinja2.TemplateSyntaxError as exc:
            raise RenderError(f"Invalid entry template: {exc}") from exc

    def render_entry(self, entry: Entry) -> str:
        try:
            text = self._entry_template.render(
                content=entry.content,
                date=entry.date,
                nonce=entry.nonce,
                section=entry.section,
                metadata=entry.metadata,
            )
        except Exception as exc:
            raise RenderError(f"{entry.path.name}: Failed to render entry: {exc}") from exc
        return text.strip()

    def render_block(self, entries: Sequence[Entry], *, header: str) -> str:
        context: dict[str, Any] = {
            "header": header,
            "entries": list(entries),
            "sections": self.group_entries(entries),
            "render_entry": self.render_entry,
            "list_item": self.fmt.list_item,
            "section_header": self.fmt.section_header,
        }
        try:
            text = self._template.render(context)
        except RenderError:
            raise
        except Exception as exc:
            raise RenderError(f"Failed to render version block: {exc}") from exc
        return text.strip()
