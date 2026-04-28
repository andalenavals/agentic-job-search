Overview
========

``agentic-job-search`` is a CLI-first job search automation project.

The package currently supports two main workflows:

* a standard search mode that returns likely official application links
* a debug and verification mode that inspects source links one by one,
  checks whether the pages still exist, and can rank the verified results
  against a candidate profile

Current capabilities
--------------------

* Search multiple public job sources from one command.
* Filter strict output down to links that look like official application pages.
* Inspect source links with live verification in ``--debug-links`` mode.
* Extract page descriptions for verified debug reports.
* Rank debug results with:

  * a simple semantic score
  * an optional local Ollama model score

* Produce:

  * standard Markdown or CSV search output
  * detailed debug reports
  * links-only action reports
  * optional email digests

Repository layout
-----------------

* ``src/job_searcher/``: package code
* ``scripts/``: helper entry points for the recurring automation flow
* ``data/``: local-only profile and SMTP configuration inputs
* ``reports/``: generated reports
* ``tests/``: unit tests

Important behavior
------------------

* ``--source all`` expands to every selectable source, including optional or
  placeholder entries that may emit warnings when not configured.
* Helper scripts always write report files, even when email delivery is skipped
  or SMTP sending fails.
* The local profile matching flow uses Ollama only when requested and available.

