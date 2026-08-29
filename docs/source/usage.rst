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

.. _documentation-format:

Documentation format
--------------------

rtfc is not tied to a documentation framework: changelog entries are written
in the documentation format of your project, and rtfc only combines them
(their content is never parsed). The :confval:`format` configuration value
selects the format, which determines the structure rtfc produces (headings,
list items, the insert marker comment). reStructuredText (``rst``) is built in
and the default. Other formats can be provided by third-party packages, through
the ``rtfc.formats`` :ref:`entry point group <packaging:entry-points>`.

The examples below use the default ``rst`` format.

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

Create a changelog entry along the changes of a pull request with the
:commands:command:`new <rtfc-new>` command. When run from a terminal,
missing values are prompted for, and the entry is opened in :envvar:`EDITOR`:

.. code-block:: console

    $ rtfc new --section bugfix --meta gh_issue=123 --content "Fix a bug."
    Created changelog/d0592011.bugfix.rtfc

Validate the configuration and all entries with the :commands:command:`check <rtfc-check>`
command, typically in CI:

.. code-block:: console

    $ rtfc check
    OK: 3 valid entries

On release, combine the entries into the changelog with the :commands:command:`build <rtfc-build>`
command. The release notes are inserted after the marker and the entry files are deleted. Use
``--dry-run`` first to preview the release notes without touching anything:

.. code-block:: console

    $ rtfc build --version 1.2.0 --dry-run
    $ rtfc build --version 1.2.0
    Updated docs/source/changelog.rst

Entries can also be :ref:`exported <export>` in alternative formats, e.g. as
markdown for GitHub or GitLab release notes.

See the :ref:`command line interface reference <cli>` for all options.


.. rubric:: Footnotes

.. [#f1] See :ref:`packaging:pyproject-tool-table` for reference.
