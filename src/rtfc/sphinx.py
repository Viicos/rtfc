"""Sphinx extension injecting the unreleased changelog entries at build time.

Add the extension to ``conf.py`` and point it at the directory holding the
rtfc configuration (relative paths are resolved against the ``conf.py``
directory)::

    extensions = ["rtfc.sphinx"]
    rtfc_config_directory = "../.."

Then use the directive where the unreleased changes should appear, typically
right above the insert marker::

    Changelog
    =========

    .. rtfc-unreleased::

    .. rtfc-insert

The entries are injected in the built documentation only. Released versions are
inserted into it by ``rtfc build``.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from textwrap import indent

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective
from sphinx.util.typing import ExtensionMetadata

from rtfc._config import ConfigError, load_config
from rtfc._entry import ENTRY_SUFFIX, EntryError, load_entries
from rtfc._format import FormatError, get_format
from rtfc._render import JinjaRenderer, RenderError

__all__ = ("UnreleasedDirective", "setup")


class UnreleasedDirective(SphinxDirective):
    """Render the unreleased changelog entries under an ``Unreleased`` heading.

    The directive content, when given, is rendered as a note admonition below
    the heading::

        .. rtfc-unreleased::

           This version is not yet released and is under active development.

    Renders nothing when there are no entries.
    """

    has_content = True

    def run(self) -> list[nodes.Node]:
        directory = Path(self.config.rtfc_config_directory)
        if not directory.is_absolute():
            directory = (Path(self.env.app.confdir) / directory).resolve()
        try:
            config = load_config(directory)
            self._note_dependencies(directory, config.directory)
            fmt = get_format(config.format)
            entries = load_entries(
                config.directory, sections=config.sections, metadata_validator=config.metadata_validator()
            )
            if not entries:
                return []
            header = fmt.unreleased_header()
            if self.content:
                note = indent("\n".join(self.content), "   ")
                header = f"{header}\n\n.. note::\n\n{note}"
            renderer = JinjaRenderer(config=config, fmt=fmt)
            block = renderer.render_block(entries, header=header)
        except (ConfigError, EntryError, FormatError, RenderError) as exc:
            raise self.error(f"rtfc: {exc}") from exc
        return self.parse_text_to_nodes(block, allow_section_headings=True)

    def _note_dependencies(self, config_directory: Path, entry_directory: Path) -> None:
        """Mark the configuration and entry files as dependencies of the document.

        This triggers a rebuild of the document when they change; new entry
        files are picked up through the entry directory modification time.
        """
        for path in (
            config_directory / "rtfc.toml",
            config_directory / "pyproject.toml",
            entry_directory,
            *entry_directory.glob(f"*{ENTRY_SUFFIX}"),
        ):
            if path.exists():
                self.env.note_dependency(str(path))


def setup(app: Sphinx) -> ExtensionMetadata:
    """Set up the extension."""
    app.add_config_value("rtfc_config_directory", default=".", rebuild="env", types=frozenset({str}))
    app.add_directive("rtfc-unreleased", UnreleasedDirective)
    return {
        "version": importlib.metadata.version("rtfc"),
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
