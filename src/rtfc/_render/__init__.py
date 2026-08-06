"""Rendering of changelog entries into version blocks.

A version block is the text added to the changelog for one release (or for the
unreleased changes): a version header followed by the rendered entries, grouped
by section. :class:`Renderer` orchestrates grouping, sorting and format
structure; how a single entry is turned into text is left to subclasses, so
that alternative template engines can be plugged in. :class:`JinjaRenderer` is
the default, rendering entries through the configured Jinja template. Entry
content is never parsed.
"""

from rtfc._render.base import Renderer, RenderError
from rtfc._render.jinja import JinjaRenderer

__all__ = ("JinjaRenderer", "RenderError", "Renderer")
