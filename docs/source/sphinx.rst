.. _sphinx_extension:

Sphinx extension
================

rtfc ships a sphinx extension rendering the *unreleased* changelog entries in
the built documentation. Entries not yet released only exist as files in
the entry directory, and the extension injects them at build time, so the
changelog page always previews the upcoming changes without the source file
ever being modified.

Setup
-----

Enable the extension in :file:`conf.py`, and point it at the directory the
rtfc configuration lives in:

.. code-block:: python

   extensions = ["rtfc.sphinx"]
   rtfc_config_directory = "../.."

.. confval:: rtfc_config_directory
   :type: string
   :default: ``"."``

   The directory the rtfc :ref:`configuration` is discovered
   in, relative to the :file:`conf.py` directory.

Usage
-----

.. rst:directive:: .. rtfc-unreleased::

   Renders the unreleased changelog entries under an ``Unreleased`` heading,
   grouped and sorted according to the :ref:`configuration`. Renders nothing
   when there are no entries.

   The directive content, when given, is rendered as a note admonition below
   the heading.

Use the directive where the unreleased changes should appear, typically right
above the insert marker:

.. code-block:: rst

   Changelog
   =========

   .. rtfc-unreleased::

      These changes are not yet released and are under active development.

   .. rtfc-insert
