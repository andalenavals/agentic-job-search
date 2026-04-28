Automation Flow
===============

Helper scripts
--------------

The repository ships with two helper scripts in ``scripts/``:

* ``send_top_llm_match_email.sh``
* ``send_top_newest_email.sh``

Both scripts:

* run across all selectable sources
* use ``--debug-links``
* inspect ``10`` links per source by default
* write a detailed report to ``reports/``
* write a links-only ``_action`` report to ``reports/``
* attempt to email the top ``5`` links only when SMTP configuration is present

The LLM script ranks by profile match. The newest script ranks by the newest
available posting dates.

Local configuration
-------------------

The scripts assume these local-only files:

* ``data/profile.txt``
* ``data/email.env``

``data/email.env`` can define the SMTP settings used by the CLI:

* ``JOB_SEARCH_SMTP_HOST``
* ``JOB_SEARCH_SMTP_PORT``
* ``JOB_SEARCH_SMTP_USER``
* ``JOB_SEARCH_SMTP_PASSWORD``
* ``JOB_SEARCH_SMTP_TLS``
* ``JOB_SEARCH_EMAIL_FROM``
* ``EMAIL_TO``

Email fallback behavior
-----------------------

If ``data/email.env`` still contains placeholder values, the helper scripts skip
email delivery and continue.

If SMTP sending fails after the report is generated, the CLI keeps the run
successful and prints a warning while preserving the report output.

Generated files
---------------

Default report targets:

* ``reports/top-llm-match-email.md``
* ``reports/top-llm-match-email_action.md``
* ``reports/top-newest-email.md``
* ``reports/top-newest-email_action.md``

