CLI Usage
=========

Standard search mode
--------------------

The basic mode collects likely official application links and renders either
Markdown or CSV.

Example:

.. code-block:: bash

   PYTHONPATH=src python3 -m job_searcher --title "data analyst" --location Berlin

Useful flags in standard mode:

* ``--title``: required search title
* ``--location``: location filter, or ``all`` for no location filter
* ``--remote``: prefer remote roles
* ``--limit``: overall result limit
* ``--include-unverified``: keep engine links that do not look official
* ``--source``: limit the run to selected sources
* ``--format {markdown,csv}``
* ``--output``: write output to a file

Debug verification mode
-----------------------

``--debug-links`` switches the CLI into source-by-source verification mode.

In this mode the package:

* asks each selected source for jobs
* takes the first ``N`` results from that source
* fetches each link
* follows redirects
* checks whether the page is reachable
* checks whether the final link still looks official
* checks whether the job title terms appear on the page

Example:

.. code-block:: bash

   PYTHONPATH=src python3 -m job_searcher \
     --title Data \
     --location all \
     --source all \
     --include-unverified \
     --debug-links \
     --debug-limit 10 \
     --output reports/debug-report.md

Useful debug flags:

* ``--debug-limit``: how many links to inspect per source
* ``--debug-timeout``: per-link verification timeout in seconds
* ``--action-output``: write a links-only report in the selected email sort order

Profile matching
----------------

When a profile is provided, debug rows can be ranked by fit.

Example:

.. code-block:: bash

   PYTHONPATH=src python3 -m job_searcher \
     --title Data \
     --location all \
     --source all \
     --include-unverified \
     --debug-links \
     --debug-limit 10 \
     --profile-file data/profile.txt \
     --ollama-model deepseek-r1:latest \
     --output reports/profile-report.md \
     --action-output reports/profile-report_action.md

Matching flags:

* ``--profile``: inline candidate profile
* ``--profile-file``: text file with candidate profile
* ``--ollama-model``: local Ollama model name
* ``--no-llm-match``: semantic score only
* ``--match-timeout``: per-request Ollama timeout

The detailed report adds ``Semantic Match`` and ``LLM Match`` columns when
profile matching is enabled.

