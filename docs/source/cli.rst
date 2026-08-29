.. _cli:

Command line interface
======================

All commands require a valid :ref:`configuration <configuration>` in the
current working directory.

.. argparse::
   :module: rtfc._cli
   :func: _docs_parser
   :prog: rtfc

Environment variables
---------------------

.. envvar:: EDITOR

   The editor ``rtfc new`` opens the created entry in, when ``--content`` is
   not given. When unset, the entry is created with a placeholder content
   to edit afterwards.
