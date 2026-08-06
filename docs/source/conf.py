# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'rtfc'
copyright = '2026-%Y, Victorien'
author = 'Victorien'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_inline_tabs",
    "sphinx_issues",
    "sphinxarg.ext",
    "rtfc.sphinx",
]

rtfc_config_directory = "../.."

templates_path = ['_templates']
exclude_patterns = []

intersphinx_mapping = {
    "packaging": ("https://packaging.python.org/en/latest", None),
}

issues_github_path = "Viicos/rtfc"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ['_static']
html_theme_options = {
    "source_repository": "https://github.com/Viicos/rtfc/",
    "source_branch": "main",
    "source_directory": "docs/source/",
}


# -- Custom directives --------------------------------------------------------

from textwrap import indent

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective


def _pyproject_variant(toml: str) -> str:
    """Derive the ``pyproject.toml`` form of an ``rtfc.toml`` example."""
    lines = []
    for line in toml.splitlines():
        if line.startswith("[[rtfc"):
            lines.append(f"[[tool.rtfc{line[len('[[rtfc') :]}")
        elif line.startswith("[rtfc"):
            lines.append(f"[tool.rtfc{line[len('[rtfc') :]}")
        else:
            lines.append(line)
    return "\n".join(lines)


class RtfcConfigExample(SphinxDirective):
    """Render a TOML configuration example as ``rtfc.toml``/``pyproject.toml`` tabs.

    The content is written in its ``rtfc.toml`` form; the ``pyproject.toml``
    variant is derived by prefixing tables with ``tool.rtfc``.
    """

    has_content = True

    def run(self) -> list[nodes.Node]:
        raw = "\n".join(self.content)
        text = ""
        for label, content in (("rtfc.toml", raw), ("pyproject.toml", _pyproject_variant(raw))):
            text += f".. tab:: :file:`{label}`\n\n   .. code-block:: toml\n\n"
            text += indent(content, "      ") + "\n\n"
        return self.parse_text_to_nodes(text)


def setup(app: Sphinx) -> None:
    app.add_directive("rtfc-config-example", RtfcConfigExample)
