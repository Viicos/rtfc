.. _configuration:

Configuration
=============

rtfc is configured in TOML, either in the ``[rtfc]`` table of an
:file:`rtfc.toml` file or in the ``[tool.rtfc]`` table of :file:`pyproject.toml`
(see :ref:`usage`). Each example below is given for both files.
Relative paths are resolved against the directory the configuration is discovered in.

.. confval:: changelog
   :type: path

   The changelog file the release notes are inserted into on release. Required;
   the file must exist and contain the insert marker comment
   (``.. rtfc-insert`` for the rst format).

   .. rtfc-config-example::

      [rtfc]
      changelog = "docs/source/changelog.rst"

.. confval:: directory
   :type: path
   :default: ``"changelog"``

   The directory holding the changelog entry files. It must exist.

   .. rtfc-config-example::

      [rtfc]
      directory = "changelog.d"

.. confval:: format
   :type: string
   :default: ``"rst"``

   The documentation format of the entries and the changelog. ``rst`` is built
   in; third-party formats are looked up in the ``rtfc.formats``
   :ref:`entry point group <packaging:entry-points>`.

   .. rtfc-config-example::

      [rtfc]
      format = "rst"

.. confval:: sections
   :type: list
   :default: the ``change``, ``feature`` and ``bugfix`` sections

   The changelog sections (entry categories), in output order. Each item is
   either a section id (its label is then derived from the id) or a table
   with ``id`` and ``label`` keys.

   .. rtfc-config-example::

      [rtfc]
      sections = [
          "deprecation",
          { id = "bugfix", label = "Bug fixes" },
      ]

.. confval:: metadata
   :type: table
   :default: empty (metadata is free-form)

   The schema of the entry metadata fields, one table per field. Once a schema
   is defined, unknown metadata fields are rejected. Each field is configured
   with:

   ``type``
       The type of the field value: ``"string"``, ``"integer"``, ``"boolean"``,
       ``"number"``, ``"date"`` or ``"array"``.
   ``items``
       The type of the array items. Required (and only allowed) when
       ``type`` is ``"array"``.
   ``required``
       Whether the field must be present on every entry (defaults to
       ``false``). Mutually exclusive with ``default``.
   ``default``
       The value applied when the field is absent.
       Mutually exclusive with ``required``

   .. rtfc-config-example::

      [rtfc.metadata.gh_issue]
      type = "integer"
      required = true

      [rtfc.metadata.contributors]
      type = "array"
      items = "string"
      default = []

.. confval:: render.template
   :type: string
   :default: the template below

   The Jinja template rendering the whole release notes of a version. The template receives:

   ``header``
       The already-formatted version header.
   ``entries``
       All the entries of the release notes.
   ``sections``
       The entries grouped by section: the unsectioned group first, then the
       configured sections in order. Each group has ``id``, ``label``
       (``None`` for the unsectioned group) and ``entries`` attributes.
   ``render_entry()``, ``list_item()``, ``section_header()``
       Functions rendering an entry through :confval:`render.entry_template`,
       wrapping text as a list item, and formatting a section heading.

   The ``sort_entries()`` filter sorts entries by the given keys: ``date``
   (the default), ``nonce``, or ``metadata.<field>``. Entries missing a
   value sorting last. The default template renders each non-empty section
   under its heading, entries sorted by date:

   .. code-block:: jinja

      {{ header }}
      {% for section in sections if section.entries %}

      {% if section.label %}
      {{ section_header(section.label) }}

      {% endif %}
      {% for entry in section.entries | sort_entries %}
      {{ list_item(render_entry(entry)) }}
      {% endfor %}
      {% endfor %}

   For example, ignoring sections and rendering a single flat list:

   .. rtfc-config-example::

      [rtfc.render]
      template = """
      {{ header }}

      {% for entry in entries | sort_entries %}
      {{ list_item(render_entry(entry)) }}
      {% endfor %}
      """

.. confval:: render.template_file
   :type: path
   :default: unset

   A file containing the release notes template, as an alternative to
   :confval:`render.template`.

   .. rtfc-config-example::

      [rtfc.render]
      template_file = "version.rst.jinja"

.. confval:: render.entry_template
   :type: string
   :default: ``"{{ content }}"``

   The Jinja template rendering a single entry, receiving ``content``,
   ``date``, ``nonce``, ``section`` and ``metadata`` in context. Mutually
   exclusive with :confval:`render.entry_template_file`.

   .. rtfc-config-example::

      [rtfc.render]
      entry_template = "{{ content }}{% if metadata.gh_issue %} (:gh:`{{ metadata.gh_issue }}`){% endif %}"

.. confval:: render.entry_template_file
   :type: path
   :default: unset

   A file containing the entry template, as an alternative to
   :confval:`render.entry_template`.

   .. rtfc-config-example::

      [rtfc.render]
      entry_template_file = "entry.rst.jinja"

.. confval:: export.<exporter>.engine
   :type: table

   :ref:`Exporters <export>`, converting the release notes to another format,
   are configured with one table per exporter id. The ``engine`` table selects
   and configures the format engine used to convert the format-specific syntax
   of the entries; its ``name`` key discriminates the engine and its remaining
   keys. The built-in ``markdown``, ``github-markdown`` and ``gitlab-markdown``
   exporters all support the ``sphinx`` engine.

   .. rtfc-config-example::

      [rtfc.export.markdown.engine]
      name = "sphinx"
      sphinx_directory = "docs/source"

.. confval:: export.<exporter>.engine.sphinx_directory
   :type: path

   The Sphinx source directory (containing :file:`conf.py`). Required.

.. TODO use  ``:confval:sphinx:html_baseurl`` once https://github.com/sphinx-doc/sphinx/issues/14117 is fixed.

.. confval:: export.<exporter>.engine.base_url
   :type: string
   :default: the ``html_baseurl`` Sphinx configuration value

   Absolute URL of the published documentation, used to resolve relative links.

   .. rtfc-config-example::

      [rtfc.export.markdown.engine]
      name = "sphinx"
      sphinx_directory = "docs/source"
      base_url = "https://rtfc.readthedocs.io/en/latest"

.. seealso::

   The :ref:`sphinx extension <sphinx_extension>` has its own configuration
   value, :confval:`rtfc_config_directory`, defined in :file:`conf.py`.
