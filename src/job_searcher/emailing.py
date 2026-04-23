from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import timezone
from email.message import EmailMessage
from email.utils import formataddr

from job_searcher.debugging import FlatDebugJob


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    use_tls: bool = True
    from_addr: str = ""
    from_name: str = "Agentic Job Search"


def email_settings_from_env(
    from_addr: str | None = None,
    from_name: str = "Agentic Job Search",
) -> EmailSettings:
    return EmailSettings(
        host=os.environ.get("JOB_SEARCH_SMTP_HOST", ""),
        port=int(os.environ.get("JOB_SEARCH_SMTP_PORT", "587")),
        username=os.environ.get("JOB_SEARCH_SMTP_USER"),
        password=os.environ.get("JOB_SEARCH_SMTP_PASSWORD"),
        use_tls=os.environ.get("JOB_SEARCH_SMTP_TLS", "true").lower() not in {"0", "false", "no"},
        from_addr=from_addr or os.environ.get("JOB_SEARCH_EMAIL_FROM", ""),
        from_name=from_name,
    )


def select_digest_jobs(
    rows: list[FlatDebugJob],
    limit: int = 5,
    sort_by: str = "match",
) -> list[FlatDebugJob]:
    selected = list(rows)
    if sort_by == "match":
        selected.sort(
            key=lambda row: (row.match.sort_score if row.match else 0, -row.index),
            reverse=True,
        )
    elif sort_by == "newest":
        selected.sort(
            key=lambda row: (
                row.job.published_at is not None,
                published_timestamp(row),
                row.match.sort_score if row.match else 0,
                -row.index,
            ),
            reverse=True,
        )
    elif sort_by == "source":
        selected.sort(key=lambda row: row.index)
    else:
        raise ValueError(f"Unknown email sort: {sort_by}")
    return selected[:limit]


def build_digest_email(
    rows: list[FlatDebugJob],
    query_title: str,
    to_addr: str,
    from_addr: str,
    from_name: str = "Agentic Job Search",
    subject: str | None = None,
    limit: int = 5,
    sort_by: str = "match",
) -> EmailMessage:
    selected = select_digest_jobs(rows, limit=limit, sort_by=sort_by)
    message = EmailMessage()
    message["To"] = to_addr
    message["From"] = formataddr((from_name, from_addr))
    message["Subject"] = subject or f"Top {len(selected)} job matches for {query_title}"
    message.set_content(render_digest_text(selected, query_title, sort_by))
    return message


def render_digest_text(rows: list[FlatDebugJob], query_title: str, sort_by: str) -> str:
    lines = [
        f"Top job results for: {query_title}",
        f"Sorted by: {sort_by}",
        "",
    ]
    if not rows:
        lines.append("No job results were available.")
        return "\n".join(lines)
    for index, row in enumerate(rows, start=1):
        final_url = row.verification.final_url or row.verification.url
        lines.extend(
            [
                f"{index}. {row.job.title}",
                f"Company: {row.job.company or 'Unknown'}",
                f"Source: {row.source}",
                f"Verdict: {row.verification.verdict}",
                f"Semantic match: {semantic_label(row)}",
                f"LLM match: {llm_label(row)}",
                f"Published: {row.job.published_at.date().isoformat() if row.job.published_at else 'unknown'}",
                f"Link: {final_url}",
                f"Description: {short_description(row.description)}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def send_email(message: EmailMessage, settings: EmailSettings) -> None:
    if not settings.host:
        raise ValueError("Missing SMTP host. Set JOB_SEARCH_SMTP_HOST or pass SMTP settings.")
    if not settings.from_addr:
        raise ValueError("Missing from address. Set JOB_SEARCH_EMAIL_FROM or pass --email-from.")
    with smtplib.SMTP(settings.host, settings.port, timeout=30) as smtp:
        if settings.use_tls:
            smtp.starttls()
        if settings.username:
            smtp.login(settings.username, settings.password or "")
        smtp.send_message(message)


def semantic_label(row: FlatDebugJob) -> str:
    if not row.match:
        return "not-run"
    return f"{row.match.semantic_score:.1f}/100"


def published_timestamp(row: FlatDebugJob) -> float:
    if not row.job.published_at:
        return 0.0
    value = row.job.published_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def llm_label(row: FlatDebugJob) -> str:
    if not row.match:
        return "not-run"
    if row.match.llm_score is None:
        return row.match.llm_error or "not-run"
    if row.match.llm_reason:
        return f"{row.match.llm_score}/100 - {row.match.llm_reason}"
    return f"{row.match.llm_score}/100"


def short_description(value: str, max_chars: int = 700) -> str:
    compacted = " ".join(value.split())
    if len(compacted) <= max_chars:
        return compacted
    return compacted[: max_chars - 1].rstrip() + "…"
