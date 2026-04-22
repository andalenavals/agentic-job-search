# agentic-job-search

MVP job search automation for collecting job postings and keeping links that look like official application pages.

The first goal is intentionally small:

1. User enters a job title and optional filters.
2. Connectors search job sources.
3. The tool keeps postings with likely official application links.
4. Results are sorted and exported as Markdown or CSV.

## Current MVP Scope

Implemented:

- Command line interface.
- Connector architecture for multiple job engines.
- Public-source connectors:
  - Bundesagentur fuer Arbeit public search API.
  - Arbeitnow public API.
  - Indeed public search cards as experimental, unverified source links.
  - LinkedIn public guest job cards as experimental, unverified source links.
  - Remotive public API.
  - Greenhouse company boards when company tokens are provided.
  - Lever company boards when company tokens are provided.
- Placeholder connectors for StepStone, Instaffo, and Glassdoor.
- Official application link heuristics.
- Markdown and CSV output.

Not implemented yet:

- Deep filtering and ranking.
- Anti-fake verification beyond official-link heuristics.
- Browser automation for engines that require interactive pages.
- Paid or authenticated APIs.

## Quick Start

Run directly from the project folder:

```bash
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --location Berlin --format markdown
```

Use specific public sources:

```bash
PYTHONPATH=src python3 -m job_searcher --title "python developer" --source arbeitnow --source remotive
```

Search selected Greenhouse or Lever company boards:

```bash
PYTHONPATH=src python3 -m job_searcher --title "backend engineer" --greenhouse stripe
```

Write results to a file:

```bash
PYTHONPATH=src python3 -m job_searcher --title "product manager" --output results.md
PYTHONPATH=src python3 -m job_searcher --title "product manager" --format csv --output results.csv
```

During early source development, include engine/source links that are not yet verified as official company application pages:

```bash
PYTHONPATH=src python3 -m job_searcher --title "engineer" --include-unverified
```

## Source Notes

Some engines named in the product idea are intentionally placeholders in the MVP:

- StepStone
- Instaffo
- Glassdoor

These sites often require JavaScript, login, strict terms, or official APIs. The project should add compliant connectors source by source instead of relying on fragile scraping.

LinkedIn and Indeed are currently experimental. These connectors read public job cards and return engine job URLs, not verified company ATS links. In strict mode, these results are filtered out. Use `--include-unverified` to inspect them:

```bash
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --location Berlin --source linkedin --include-unverified
PYTHONPATH=src python3 -m job_searcher --title "data analyst" --location Berlin --source indeed --include-unverified
```

## Development

Run a smoke test:

```bash
PYTHONPATH=src python3 -m job_searcher --title "engineer" --source remotive --limit 5
```
