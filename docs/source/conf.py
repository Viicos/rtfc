# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from textwrap import indent

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "rtfc"
copyright = "2026-%Y, Victorien"
author = "Victorien"
release = "0.1.0"

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

exclude_patterns = []

intersphinx_mapping = {
    "packaging": ("https://packaging.python.org/en/latest", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
}

issues_github_path = "Viicos/rtfc"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_baseurl = "https://rtfc.readthedocs.io/en/latest/"
html_theme = "furo"
html_theme_options = {
    "source_repository": "https://github.com/Viicos/rtfc/",
    "source_branch": "main",
    "source_directory": "docs/source/",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/Viicos/rtfc/",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
}


# -- Custom directives --------------------------------------------------------


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
