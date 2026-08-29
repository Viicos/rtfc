"""The sphinx format engine, converting sphinx-flavored rst to markdown.

The rendered release notes are written as an orphan document inside the project's sphinx source directory
and built with the project's own ``conf.py`` so custom roles, extensions and cross-references can resolve.
Nodes without a markdown equivalent are left as is.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urljoin, urlsplit

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.errors import SphinxError
from sphinx.util.docutils import SphinxTranslator, docutils_namespace, patch_docutils

from rtfc._config import SphinxEngineConfig
from rtfc._export import ExportError

if TYPE_CHECKING:
    from sphinx.util.typing import ExtensionMetadata

__all__ = ("export_markdown", "setup")

_DOCNAME = "_rtfc-export"

_ADMONITION_KINDS = {
    "note": "NOTE",
    "seealso": "NOTE",
    "hint": "TIP",
    "tip": "TIP",
    "important": "IMPORTANT",
    "attention": "WARNING",
    "warning": "WARNING",
    "caution": "CAUTION",
    "danger": "CAUTION",
    "error": "CAUTION",
}
"""Admonition kind per docutils admonition type."""


class _MarkdownTranslator(SphinxTranslator):
    """Translates a resolved doctree into markdown.

    Nodes without a markdown equivalent are left as is.
    """

    builder: MarkdownExportBuilder

    def __init__(self, document: nodes.document, builder: MarkdownExportBuilder) -> None:
        super().__init__(document, builder)
        self._blocks: list[str] = []
        self._inline: list[str] = []
        self._section_depth = 0
        self._references: list[str | None] = []

    def finalize(self) -> str:
        return "\n\n".join(self._blocks)

    def _push_block(self, text: str) -> None:
        if text.strip():
            self._blocks.append(text)

    def _translate_children(self, node: nodes.Element) -> str:
        """Translate the children of ``node`` in a nested translator, e.g. for list items."""
        translator = _MarkdownTranslator(self.document, self.builder)
        translator._section_depth = self._section_depth
        for child in node.children:
            child.walkabout(translator)
        return translator.finalize()

    def _url(self, uri: str) -> str:
        if self.builder.base_url is not None and not urlsplit(uri).scheme:
            return urljoin(f"{self.builder.base_url.rstrip('/')}/", uri)
        return uri

    # Document structure.

    def visit_document(self, node: nodes.document) -> None:
        pass

    def depart_document(self, node: nodes.document) -> None:
        pass

    def visit_section(self, node: nodes.Element) -> None:
        self._section_depth += 1

    def depart_section(self, node: nodes.Element) -> None:
        self._section_depth -= 1

    def visit_title(self, node: nodes.Element) -> None:
        self._inline.clear()

    def depart_title(self, node: nodes.Element) -> None:
        self._push_block(f"{'#' * max(self._section_depth, 1)} {''.join(self._inline).strip()}")
        self._inline.clear()

    def visit_paragraph(self, node: nodes.Element) -> None:
        pass

    def depart_paragraph(self, node: nodes.Element) -> None:
        self._push_block("".join(self._inline).strip())
        self._inline.clear()

    def visit_bullet_list(self, node: nodes.Element) -> None:
        self._render_list(node, lambda index: "- ")
        raise nodes.SkipNode

    def visit_enumerated_list(self, node: nodes.Element) -> None:
        self._render_list(node, lambda index: f"{index + 1}. ")
        raise nodes.SkipNode

    def _render_list(self, node: nodes.Element, marker: Any) -> None:
        items = []
        for index, item in enumerate(node.children):
            text = self._translate_children(cast("nodes.Element", item))
            prefix = marker(index)
            first, *rest = text.split("\n")
            lines = [f"{prefix}{first}", *((" " * len(prefix) + line).rstrip() for line in rest)]
            items.append("\n".join(lines))
        self._push_block("\n".join(items))

    def visit_literal_block(self, node: nodes.Element) -> None:
        language = node.get("language", "")
        language = "" if language in ("default", "none") else language
        self._push_block(f"```{language}\n{node.astext()}\n```")
        raise nodes.SkipNode

    def visit_block_quote(self, node: nodes.Element) -> None:
        text = self._translate_children(node)
        self._push_block("\n".join(f"> {line}".rstrip() for line in text.split("\n")))
        raise nodes.SkipNode

    def visit_transition(self, node: nodes.Element) -> None:
        self._push_block("---")
        raise nodes.SkipNode

    def visit_Admonition(self, node: nodes.Element) -> None:
        # The label syntax is dialect-specific and provided by the exporter:
        label = self.builder.admonition_label(_ADMONITION_KINDS.get(node.tagname or "", "NOTE"))
        text = self._translate_children(node)
        lines = [f"> {label}", *(f"> {line}".rstrip() for line in text.split("\n"))]
        self._push_block("\n".join(lines))
        raise nodes.SkipNode

    # Inline nodes.

    def visit_Text(self, node: nodes.Text) -> None:
        self._inline.append(node.astext())

    def depart_Text(self, node: nodes.Text) -> None:
        pass

    def visit_emphasis(self, node: nodes.Element) -> None:
        self._inline.append("*")

    def depart_emphasis(self, node: nodes.Element) -> None:
        self._inline.append("*")

    def visit_strong(self, node: nodes.Element) -> None:
        self._inline.append("**")

    def depart_strong(self, node: nodes.Element) -> None:
        self._inline.append("**")

    def visit_title_reference(self, node: nodes.Element) -> None:
        self._inline.append("*")

    def depart_title_reference(self, node: nodes.Element) -> None:
        self._inline.append("*")

    def visit_literal(self, node: nodes.Element) -> None:
        text = node.astext()
        self._inline.append(f"``{text}``" if "`" in text else f"`{text}`")
        raise nodes.SkipNode

    def visit_reference(self, node: nodes.Element) -> None:
        uri = node.get("refuri")
        self._references.append(self._url(uri) if uri else None)
        if uri:
            self._inline.append("[")

    def depart_reference(self, node: nodes.Element) -> None:
        url = self._references.pop()
        if url is not None:
            self._inline.append(f"]({url})")

    def visit_image(self, node: nodes.Element) -> None:
        self._inline.append(f"![{node.get('alt', '')}]({self._url(node.get('uri', ''))})")
        raise nodes.SkipNode

    # Invisible nodes.

    def visit_comment(self, node: nodes.Element) -> None:
        raise nodes.SkipNode

    def visit_system_message(self, node: nodes.Element) -> None:
        raise nodes.SkipNode

    def visit_target(self, node: nodes.Element) -> None:
        raise nodes.SkipNode

    # Everything else degrades to its plain text.

    def unknown_visit(self, node: nodes.Node) -> None:
        text = node.astext()
        if isinstance(node, nodes.Inline):
            self._inline.append(text)
        else:
            self._push_block(text)
        raise nodes.SkipNode


class MarkdownExportBuilder(Builder):
    """Builds the export document into markdown, stored on :attr:`markdown`."""

    name = "rtfc-export"
    format = "markdown"
    epilog = ""
    allow_parallel = False

    base_url: str | None = None
    admonition_label: Callable[[str], str] = staticmethod(lambda kind: f"**{kind.capitalize()}**")
    markdown: str | None = None

    def get_outdated_docs(self) -> list[str]:
        return []

    def get_target_uri(self, docname: str, typ: str | None = None) -> str:
        # html-style URIs, so that resolved references can be joined onto the
        # published documentation base URL:
        return f"{docname}.html"

    def prepare_writing(self, docnames: object) -> None:
        pass

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        if docname != _DOCNAME:
            return
        translator = _MarkdownTranslator(doctree, self)
        doctree.walkabout(translator)
        self.markdown = translator.finalize()


def export_markdown(engine_config: SphinxEngineConfig, notes: str, *, admonition_label: Callable[[str], str]) -> str:
    """Convert rendered release notes to markdown through the project's sphinx build.

    Args:
        engine_config: The ``sphinx`` engine configuration.
        notes: The rendered release notes, in the sphinx source format.
        admonition_label: A callable taking an admonition kind (e.g. ``'NOTE'``)
            and returning the label opening the block quote the admonition is
            rendered as (e.g. ``'[!NOTE]'``).

    Raises:
        ExportError: If the sphinx build fails.
    """
    directory = engine_config.sphinx_directory
    if not (directory / "conf.py").is_file():
        raise ExportError(f"No sphinx configuration found in {str(directory)!r}")

    source = directory / f"{_DOCNAME}.rst"
    with tempfile.TemporaryDirectory() as build_directory:
        # An orphan document, so sphinx does not warn about it missing from a toctree:
        source.write_text(f":orphan:\n\n{notes}\n", encoding="utf-8")
        try:
            with patch_docutils(str(directory)), docutils_namespace():
                app = Sphinx(
                    srcdir=str(directory),
                    confdir=str(directory),
                    outdir=str(Path(build_directory) / "output"),
                    doctreedir=str(Path(build_directory) / "doctrees"),
                    buildername="rtfc-export",
                    status=None,
                    warning=sys.stderr,
                )
                builder = cast("MarkdownExportBuilder", app.builder)
                builder.base_url = engine_config.base_url or app.config.html_baseurl or None
                builder.admonition_label = admonition_label
                app.build()
        except SphinxError as exc:
            raise ExportError(f"The sphinx build failed: {exc}") from exc
        finally:
            source.unlink(missing_ok=True)
    if builder.markdown is None:
        raise ExportError("The export document was not built")
    return builder.markdown


def setup(app: Sphinx) -> ExtensionMetadata:
    """Register the export builder, through the ``sphinx.builders`` entry point group."""
    app.add_builder(MarkdownExportBuilder)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
