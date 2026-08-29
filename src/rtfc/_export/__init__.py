"""Export of release notes to other formats.

Exporters convert rendered release notes (written in the documentation format of the project)
to another format, e.g. GitHub-flavored markdown. The conversion of the format-specific syntax
of the entries (roles, references, ...) is delegated to a *format engine*: each exporter declares
the engines it supports, and the engine to use is selected with the ``engine`` table of the
exporter configuration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from rtfc._config import Config, EngineConfig, ExporterConfig, SphinxEngineConfig

__all__ = (
    "ExportError",
    "Exporter",
    "GitHubMarkdownExporter",
    "GitLabMarkdownExporter",
    "MarkdownExporter",
    "get_exporter",
)


class ExportError(Exception):
    """Raised when the export fails."""


class Exporter(ABC):
    """Exports rendered release notes to another format."""

    id: ClassVar[str]
    """Id of the exporter, as used in the export configuration."""

    format_engines: ClassVar[dict[str, type[EngineConfig]]]
    """The format engines supported by the exporter, mapping the engine name to its
    configuration schema."""

    def __init__(self, config: Config, exporter_config: ExporterConfig) -> None:
        self.config = config
        self.exporter_config = exporter_config

    @abstractmethod
    def export(self, notes: str) -> str:
        """Convert rendered release notes to the exporter's format.

        Raises:
            ExportError: If the conversion fails.
        """


class MarkdownExporter(Exporter):
    """Exports release notes to `CommonMark <https://spec.commonmark.org/>`_ markdown."""

    id: ClassVar[str] = "markdown"
    format_engines: ClassVar[dict[str, type[EngineConfig]]] = {"sphinx": SphinxEngineConfig}

    def admonition_label(self, kind: str) -> str:
        """Format the label opening an admonition block quote.

        ``kind`` is one of ``'NOTE'``, ``'TIP'``, ``'IMPORTANT'``,
        ``'WARNING'`` or ``'CAUTION'``. Subclasses override this to use
        dialect-specific admonition syntax.
        """
        return f"**{kind.capitalize()}**"

    def export(self, notes: str) -> str:
        # The only supported engine — 'sphinx', enforced by get_exporter — is
        # imported lazily, as sphinx is an optional dependency:
        engine = self.exporter_config.engine
        assert isinstance(engine, SphinxEngineConfig)
        try:
            from rtfc._export import _sphinx  # noqa: PLC0415
        except ImportError as exc:
            raise ExportError("sphinx must be installed to use the 'sphinx' format engine") from exc
        return _sphinx.export_markdown(engine, notes, admonition_label=self.admonition_label)


class GitHubMarkdownExporter(MarkdownExporter):
    """Exports release notes to `GitHub Flavored Markdown <https://github.github.com/gfm/>`_.

    .. seealso::
        The `GitHub writing documentation <https://docs.github.com/en/get-started/writing-on-github>`_.
    """

    id: ClassVar[str] = "github-markdown"

    def admonition_label(self, kind: str) -> str:
        # Use alerts (https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts):
        return f"[!{kind}]"


class GitLabMarkdownExporter(MarkdownExporter):
    """Exports release notes to `GitLab Flavored Markdown <https://docs.gitlab.com/user/markdown/>`_."""

    id: ClassVar[str] = "gitlab-markdown"

    def admonition_label(self, kind: str) -> str:
        # Use alerts (https://docs.gitlab.com/user/markdown/#alerts):
        return f"[!{kind.lower()}]"


_EXPORTERS: dict[str, type[Exporter]] = {
    exporter.id: exporter for exporter in (MarkdownExporter, GitHubMarkdownExporter, GitLabMarkdownExporter)
}


def get_exporter(config: Config, exporter_id: str) -> Exporter:
    """Resolve a configured exporter by id.

    Raises:
        ExportError: If the exporter is unknown, not configured, or its
            configured format engine is not supported.
    """
    exporter_class = _EXPORTERS.get(exporter_id)
    if exporter_class is None:
        available = ", ".join(map(repr, _EXPORTERS))
        raise ExportError(f"Unknown exporter {exporter_id!r} (available: {available})")
    exporter_config = config.export.get(exporter_id)
    if exporter_config is None:
        raise ExportError(f"The {exporter_id!r} exporter is not configured")
    if exporter_config.engine.name not in exporter_class.format_engines:
        supported = ", ".join(map(repr, exporter_class.format_engines))
        raise ExportError(
            f"Format engine {exporter_config.engine.name!r} is not supported by the {exporter_id!r} exporter "
            f"(supported: {supported})"
        )
    return exporter_class(config, exporter_config)
