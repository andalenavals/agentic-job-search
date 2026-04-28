Sources
=======

Default sources
---------------

When no ``--source`` flag is passed, the CLI uses these built-in public sources:

* ``agentur``
* ``arbeitnow``
* ``berlinstartupjobs``
* ``bund-de``
* ``experis``
* ``glassdoor``
* ``indeed``
* ``interamt``
* ``jobvector``
* ``karriere-nrw``
* ``kununu``
* ``linkedin``
* ``remote-com``
* ``remotive``
* ``stepstone``
* ``xing``

Selectable extras
-----------------

These are selectable, but not part of the default source set:

* ``google``: requires ``GOOGLE_SEARCH_API_KEY`` and
  ``GOOGLE_SEARCH_ENGINE_ID``
* ``instaffo``: placeholder source that currently returns a warning

Company-board integrations
--------------------------

These are enabled through dedicated flags instead of ``--source``:

* ``--greenhouse``
* ``--lever``
* ``--ashby``
* ``--personio``
* ``--smartrecruiters``
* ``--workday``

Experimental and strict-mode behavior
-------------------------------------

The following sources currently return public job-board links rather than
direct company ATS links:

* ``berlinstartupjobs``
* ``experis``
* ``glassdoor``
* ``indeed``
* ``jobvector``
* ``kununu``
* ``linkedin``
* ``stepstone``
* ``xing``

In normal strict mode, links that do not look like official application pages
are filtered out. Use ``--include-unverified`` to inspect them directly.

