.. _usage:

Usage
=====

rtfc can be used a :ref:`command line interface <cli>`. A configuration file *must* be defined
where the CLI is invoked. rtfc can be configured in to ways:

rtfc.toml
---------

:file:`rtfc.toml` has the highest priority.

.. code-block:: toml

    [rtfc]
    changelog = "docs/source/changelog.rst"

pyproject.toml
--------------

The ``[tool.rtfc]`` table can be used in the :file:`pyproject.toml` of your project [#f1]_:

.. code-block:: toml

    [tool.rtfc]
    changelog = "docs/source/changelog.rst"


``changelog`` is the only required configuration value. See :ref:`configuration` for more details.

Setting up a project
--------------------

Besides the configuration file, rtfc expects two things to exist:

- the :confval:`entry directory <directory>` (``changelog/`` by default),
  holding the changelog entry files until they are released.
- the :confval:`changelog file <changelog>`, containing the insert marker
  comment after which released versions are inserted:

  .. code-block:: rst

     Changelog
     =========

     .. rtfc-unreleased::

     .. rtfc-insert

  The :rst:dir:`rtfc-unreleased` directive is optional, it renders the
  unreleased entries when building the documentation with the :ref:`sphinx
  extension <sphinx_extension>`.

Workflow
--------

Create a changelog entry along the changes of a pull request. When run from
a terminal, missing values are prompted for, and the entry is opened in
:envvar:`EDITOR`:

.. code-block:: console

    $ rtfc new --section bugfix --meta gh_issue=123 --content "Fix a bug."
    Created changelog/d0592011.bugfix.rtfc

Validate the configuration and all entries, typically in CI:

.. code-block:: console

    $ rtfc check
    OK: 3 valid entries

On release, combine the entries into the changelog. The version block is
inserted after the marker and the entry files are deleted. Use ``--dry-run``
first to preview the block without touching anything:

.. code-block:: console

    $ rtfc build --version 1.2.0 --dry-run
    $ rtfc build --version 1.2.0
    Updated docs/source/changelog.rst

See the :ref:`command line interface reference <cli>` for all options.


.. rubric:: Footnotes

.. [#f1] See :ref:`packaging:pyproject-tool-table` for reference.
