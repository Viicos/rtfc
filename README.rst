====
rtfc
====

|Pythons| |PyPI| |Docs| |Ruff|

.. |Pythons| image:: https://img.shields.io/pypi/pyversions/rtfc.svg
  :alt: Supported Python versions
  :target: https://pypi.org/project/rtfc/

.. |PyPI| image:: https://img.shields.io/pypi/v/rtfc.svg
  :alt: PyPI - Version
  :target: https://pypi.org/project/rtfc/

.. |Docs| image:: https://img.shields.io/readthedocs/rtfc.svg
  :alt: Documentation status
  :target: https://rtfc.readthedocs.io

.. |Ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
  :alt: Ruff
  :target: https://github.com/astral-sh/ruff

*Read the freaking changelog* is a tool to manage changelogs and versioning.

As the name implies, rtfc helps you produce clear, well-structured changelogs,
leaving your users no excuse for being surprised by what changed between releases.

rtfc is heavily inspired by the great `Towncrier`_ project.

.. _`Towncrier`: https://towncrier.readthedocs.io/en/stable/

Installation
------------

From PyPI:

.. code:: bash

    pip install rtfc

Usage
-----

Configure rtfc in the ``[tool.rtfc]`` table of your ``pyproject.toml`` (or in
an ``rtfc.toml`` file), and add the insert marker to your changelog document:

.. code:: toml

    [tool.rtfc]
    changelog = "docs/source/changelog.rst"

.. code:: rst

    Changelog
    =========

    .. rtfc-insert

Changelog entries are individual files created along the changes of a pull
request, avoiding the merge conflicts a shared changelog file causes:

.. code:: console

    $ rtfc new --section bugfix --meta gh_issue=123 --content "Fix a bug."
    Created changelog/d0592011.bugfix.rtfc

Each entry holds a TOML frontmatter and the change description, written in the
documentation format of your project:

.. code:: text

    +++
    date = 2026-08-06
    nonce = "d0592011"
    section = "bugfix"

    [metadata]
    gh_issue = 123
    +++
    Fix a bug.

Validate the configuration and the entries, typically in CI:

.. code:: console

    $ rtfc check
    OK: 1 valid entries

On release, combine the entries into the changelog. The release notes are
inserted after the marker, and the entry files are deleted:

.. code:: console

    $ rtfc build --version 1.2.0
    Updated docs/source/changelog.rst

A sphinx extension is also provided, rendering the not-yet-released entries
when building your documentation.
