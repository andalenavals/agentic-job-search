# agentic-job-search

CLI job search automation for collecting job postings, checking link quality,
ranking against a candidate profile, and optionally emailing curated results.

Project page: [andalenavals.github.io/agentic-job-search](https://andalenavals.github.io/agentic-job-search/)

The package currently supports two complementary workflows:

1. standard search output for likely official application links
2. source-by-source debug verification with detailed reports, profile ranking,
   links-only action reports, and optional email delivery

## What It Does

- Searches multiple public job sources from one command.
- Filters strict results down to links that look like official application pages.
- Verifies source links in `--debug-links` mode by fetching them live.
- Extracts job descriptions from the source data or verified page content.
- Ranks verified jobs with:
  - a simple semantic score
  - an optional local Ollama score
- Produces:
  - Markdown or CSV search output
  - detailed debug reports
  - links-only `_action` reports
  - optional top-N email digests

## Quick Start

Run a standard search:

```bash
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --location Berlin
```

Write standard output to a file:

```bash
PYTHONPATH=src python3 -m job_searcher --title "product manager" --output results.md
PYTHONPATH=src python3 -m job_searcher --title "product manager" --format csv --output results.csv
```

Search specific public sources:

```bash
PYTHONPATH=src python3 -m job_searcher --title "python developer" --source arbeitnow --source remotive
```

Search all selectable sources without a location filter:

```bash
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --location all --source all --limit 50
```

Search selected company boards:

```bash
PYTHONPATH=src python3 -m job_searcher --title "backend engineer" --greenhouse stripe
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --ashby acme
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --personio acme
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --smartrecruiters Acme
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --workday https://acme.wd1.myworkdayjobs.com/careers
```

## Standard Search Mode

The basic mode returns likely official application links in Markdown or CSV.

Useful flags:

- `--title` required search title
- `--location` location filter, or `all` for no location filter
- `--remote` prefer remote roles
- `--limit` overall result limit
- `--include-unverified` keep engine links that do not look official
- `--source` repeatable public source selector
- `--format {markdown,csv}`
- `--output`

## Debug Verification Mode

`--debug-links` switches the CLI into source-by-source verification mode.

In this mode the package:

- queries each selected source independently
- takes the first `N` jobs from that source
- fetches each link and follows redirects
- records whether the page is reachable
- checks whether the final URL still looks official
- checks whether the page content mentions the job title
- builds detailed Markdown reports

Example:

```bash
PYTHONPATH=src python3 -m job_searcher \
  --title Data \
  --location all \
  --source all \
  --include-unverified \
  --debug-links \
  --debug-limit 10 \
  --debug-timeout 8 \
  --output reports/debug-report.md
```

Useful debug flags:

- `--debug-limit`
- `--debug-timeout`
- `--action-output`

## Profile Matching

When a profile is provided, debug rows can be ranked by fit.

The report adds:

- `Semantic Match`
- `LLM Match`

Example:

```bash
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
```

Semantic-only run:

```bash
PYTHONPATH=src python3 -m job_searcher \
  --title Data \
  --location all \
  --source all \
  --include-unverified \
  --debug-links \
  --debug-limit 10 \
  --profile "Data analyst with Python, SQL, dashboards, analytics, and ML experience" \
  --no-llm-match \
  --output reports/profile-report.md \
  --action-output reports/profile-report_action.md
```

Matching flags:

- `--profile`
- `--profile-file`
- `--ollama-model`
- `--no-llm-match`
- `--match-timeout`

## Email and Action Reports

The detailed report is written with `--output`.

The links-only report is written with `--action-output` and follows the same
selection order as the email digest.

Email-related flags:

- `--email-to`
- `--email-from`
- `--email-subject`
- `--email-top`
- `--email-sort {match,newest,source}`

If SMTP sending fails, the CLI keeps the run successful and preserves the report
output.

## Helper Scripts

Helper entry points live in [`scripts/`](/Users/andres/git_repos/agentic-job-search/scripts), and local-only profile / SMTP inputs live in [`data/`](/Users/andres/git_repos/agentic-job-search/data). The scripts use `data/profile.txt` and `data/email.env`.

Main helper scripts:

- [`send_top_llm_match_email.sh`](/Users/andres/git_repos/agentic-job-search/scripts/send_top_llm_match_email.sh): all selectable sources, `10` checked links per source, profile ranking, detailed report, `_action` report, and email when configured.
- [`send_top_newest_email.sh`](/Users/andres/git_repos/agentic-job-search/scripts/send_top_newest_email.sh): all selectable sources, `10` checked links per source, newest-first selection, detailed report, `_action` report, and email when configured.

Default outputs:

- `reports/top-llm-match-email.md`
- `reports/top-llm-match-email_action.md`
- `reports/top-newest-email.md`
- `reports/top-newest-email_action.md`

If `data/email.env` still contains placeholder values, the helper scripts skip
email delivery and continue generating reports.

## Source Catalog

Default sources when no `--source` is passed:

- `agentur`
- `arbeitnow`
- `berlinstartupjobs`
- `bund-de`
- `experis`
- `glassdoor`
- `indeed`
- `interamt`
- `jobvector`
- `karriere-nrw`
- `kununu`
- `linkedin`
- `remote-com`
- `remotive`
- `stepstone`
- `xing`

Selectable extras:

- `google` requires `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`
- `instaffo` is currently a placeholder source

Company-board integrations:

- `--greenhouse`
- `--lever`
- `--ashby`
- `--personio`
- `--smartrecruiters`
- `--workday`

Experimental public job-board connectors:

- `berlinstartupjobs`
- `experis`
- `glassdoor`
- `indeed`
- `jobvector`
- `kununu`
- `linkedin`
- `stepstone`
- `xing`

These sources return public job-board links, not direct company ATS links. In
strict mode they are filtered out unless `--include-unverified` is passed.

Remote.com returns official apply links when available:

```bash
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --source remote-com --remote
```

Google uses the official Programmable Search JSON API:

```bash
export GOOGLE_SEARCH_API_KEY="..."
export GOOGLE_SEARCH_ENGINE_ID="..."
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --location Berlin --source google --limit 5
```

Public-sector sources:

```bash
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --source bund-de --limit 5
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --source interamt --limit 5
PYTHONPATH=src python3 -m job_searcher --title "Verwaltungs" --source karriere-nrw --limit 5
```

## Configuration

Local-only helper-script inputs live in:

- [`data/profile.txt`](/Users/andres/git_repos/agentic-job-search/data)
- [`data/email.env`](/Users/andres/git_repos/agentic-job-search/data)

SMTP settings:

- `JOB_SEARCH_SMTP_HOST`
- `JOB_SEARCH_SMTP_PORT`
- `JOB_SEARCH_SMTP_USER`
- `JOB_SEARCH_SMTP_PASSWORD`
- `JOB_SEARCH_SMTP_TLS`
- `JOB_SEARCH_EMAIL_FROM`
- `EMAIL_TO`

## Documentation

Sphinx source files live in [`docs/`](/Users/andres/git_repos/agentic-job-search/docs).

GitHub Pages documentation is published at:
[andalenavals.github.io/agentic-job-search](https://andalenavals.github.io/agentic-job-search/)

## Development

Run the unit suite:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests
```

Run a smoke test:

```bash
PYTHONPATH=src python3 -m job_searcher --title "engineer" --source remotive --limit 5
```
