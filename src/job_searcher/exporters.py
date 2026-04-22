from __future__ import annotations

import csv
import io

from job_searcher.models import JobPosting


def to_markdown(jobs: list[JobPosting]) -> str:
    if not jobs:
        return "No likely official application links found.\n"
    lines = [
        "| Title | Company | Location | Source | Link |",
        "| --- | --- | --- | --- | --- |",
    ]
    for job in jobs:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(job.title),
                    escape_md(job.company),
                    escape_md(job.location or ""),
                    escape_md(job.source),
                    f"[Apply]({job.best_url})",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def to_csv(jobs: list[JobPosting]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["title", "company", "location", "source", "url", "published_at", "tags"],
    )
    writer.writeheader()
    for job in jobs:
        writer.writerow(
            {
                "title": job.title,
                "company": job.company,
                "location": job.location or "",
                "source": job.source,
                "url": job.best_url,
                "published_at": job.published_at.isoformat() if job.published_at else "",
                "tags": ", ".join(job.tags),
            }
        )
    return output.getvalue()


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
