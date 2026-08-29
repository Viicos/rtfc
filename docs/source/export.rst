.. _export:

Exporting release notes
=======================

Besides being inserted into the changelog document, the release notes of a
version can be *exported* to another format (typically markdown).

This is particularly useful when publishing release notes in separate places,
e.g. `GitHub releases <https://docs.github.com/en/repositories/releasing-projects-on-github>`_.

rtfc supports multiple exporters (see below). The exporter to use must first be
:confval:`configured <export.<exporter>.engine>`, e.g. the ``github-markdown``
exporter with the ``sphinx`` format engine:

.. rtfc-config-example::

   [rtfc.export.github-markdown.engine]
   name = "sphinx"
   sphinx_directory = "docs/source"

The :commands:command:`export <rtfc-export>` command can then be used to produce
the exported release notes:

.. code-block:: console

    $ rtfc export github-markdown --version 1.2.0 > release-notes.md

Run the export *before* ``rtfc build``, which deletes the entry files on
release.

Exporters and format engines
----------------------------

Exporters are responsible for converting changelog entries (present in your
:confval:`entry directory <directory>`) into a single text block, that can then
be published separately. An exporter is defined for a specific
:ref:`documentation format <documentation-format>`, and delegates the conversion
of the format-specific syntax to a *format engine*.

A *format engine* encapsulates the logic required to run your documentation engine/framework.
While :ref:`formats <documentation-format>` are agnostic of the documentation framework [#f1]_,
exporters need to use the semantics of your documentation engine, for example to resolve
references as HTML links.

rtfc provides hree built in exporters:

``markdown``
    `CommonMark <https://spec.commonmark.org/>`_ output. Admonitions are
    rendered as block quotes opened by a bold label.
``github-markdown``
    `GitHub Flavored Markdown <https://github.github.com/gfm/>`_ output,
    extended with the GitHub markdown extensions. Suitable for
    `GitHub releases <https://docs.github.com/en/repositories/releasing-projects-on-github>`_.
``gitlab-markdown``
    `GitLab Flavored Markdown <https://docs.gitlab.com/user/markdown/>`_ output. Suitable for
    `GitHub releases <https://docs.gitlab.com/user/project/releases/>`_.

All three support the ``sphinx`` format engine.

The sphinx engine
-----------------

The ``sphinx`` engine requires `Sphinx <https://www.sphinx-doc.org/>`_ to be
installed, and converts the Sphinx-flavored rst of the entries by building
them through the project's own Sphinx documentation (i.e. by using the project's
:ref:`Sphinx configuration <sphinx:build-config>`). Headings, paragraphs,
lists, code blocks, inline markup, links, images and admonitions are
supported. Other nodes are left as is. Relative links are joined onto
the :confval:`base URL <export.<exporter>.engine.base_url>` of the
published documentation.

.. rtfc-config-example::

   [rtfc.export.github-markdown.engine]
   name = "sphinx"
   sphinx_directory = "docs/source"
   base_url = "https://rtfc.readthedocs.io/en/latest"

.. note::

   Each export runs a Sphinx build of the whole project, as resolving
   cross-references requires the complete environment.

.. rubric:: Footnotes

.. [#f1] For instance, the builtin ``rst`` format doesn't necessarily assume
         `Sphinx <https://www.sphinx-doc.org/>`_ is used.
