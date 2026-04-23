from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from job_searcher.models import JobPosting, SearchQuery
from job_searcher.official_links import is_likely_official_application
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


@dataclass(frozen=True)
class LinkVerification:
    url: str
    final_url: str
    reachable: bool
    status_code: int | None
    content_type: str
    official_like: bool
    title_found: bool
    verdict: str
    error: str = ""


@dataclass(frozen=True)
class DebuggedJob:
    job: JobPosting
    verification: LinkVerification


@dataclass(frozen=True)
class SourceDebugResult:
    source: str
    jobs: tuple[DebuggedJob, ...]
    warnings: tuple[str, ...] = ()


Verifier = Callable[[JobPosting, SearchQuery, int], LinkVerification]


def debug_sources(
    sources: Iterable[JobSource],
    query: SearchQuery,
    per_source_limit: int = 5,
    timeout: int = 10,
    verifier: Verifier | None = None,
) -> list[SourceDebugResult]:
    verify = verifier or verify_job_link
    results: list[SourceDebugResult] = []
    for source in sources:
        report = SearchReport()
        debugged_jobs: list[DebuggedJob] = []
        try:
            jobs = source.search(query, report)
            for job in jobs:
                if not job.best_url:
                    continue
                debugged_jobs.append(DebuggedJob(job, verify(job, query, timeout)))
                if len(debugged_jobs) >= per_source_limit:
                    break
        except Exception as exc:  # Defensive: debug mode should keep inspecting later sources.
            report.warn(f"Skipped {source.name}: {exc}")
        results.append(
            SourceDebugResult(
                source=source_label(source),
                jobs=tuple(debugged_jobs),
                warnings=tuple(report.warnings),
            )
        )
    return results


def source_label(source: JobSource) -> str:
    token = getattr(source, "company_token", None) or getattr(source, "site_url", None)
    return f"{source.name}:{token}" if token else source.name


def verify_job_link(job: JobPosting, query: SearchQuery, timeout: int = 10) -> LinkVerification:
    url = job.best_url
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 (compatible; agentic-job-search/0.1)",
    }
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = int(getattr(response, "status", response.getcode()))
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            body = response.read(250_000)
            charset = response.headers.get_content_charset() or "utf-8"
            text = body.decode(charset, "replace")
    except HTTPError as exc:
        final_url = exc.geturl() or url
        return build_verification(
            url=url,
            final_url=final_url,
            reachable=False,
            status_code=exc.code,
            content_type=exc.headers.get("Content-Type", "") if exc.headers else "",
            official_like=official_url(url, final_url, job.company),
            title_found=False,
            error=str(exc),
        )
    except (URLError, TimeoutError, ValueError) as exc:
        return build_verification(
            url=url,
            final_url=url,
            reachable=False,
            status_code=None,
            content_type="",
            official_like=official_url(url, url, job.company),
            title_found=False,
            error=str(exc),
        )

    return build_verification(
        url=url,
        final_url=final_url,
        reachable=200 <= status_code < 400,
        status_code=status_code,
        content_type=content_type,
        official_like=official_url(url, final_url, job.company),
        title_found=content_mentions_job(text, job, query),
    )


def build_verification(
    url: str,
    final_url: str,
    reachable: bool,
    status_code: int | None,
    content_type: str,
    official_like: bool,
    title_found: bool,
    error: str = "",
) -> LinkVerification:
    if not reachable:
        verdict = "missing"
    elif official_like and title_found:
        verdict = "verified"
    elif official_like:
        verdict = "official-but-title-not-found"
    elif title_found:
        verdict = "exists-unverified"
    else:
        verdict = "suspicious"
    return LinkVerification(
        url=url,
        final_url=final_url,
        reachable=reachable,
        status_code=status_code,
        content_type=content_type,
        official_like=official_like,
        title_found=title_found,
        verdict=verdict,
        error=error,
    )


def official_url(url: str, final_url: str, company: str) -> bool:
    return is_likely_official_application(url, company) or is_likely_official_application(
        final_url,
        company,
    )


def content_mentions_job(text: str, job: JobPosting, query: SearchQuery) -> bool:
    normalized = normalize_text(text)
    if all_terms_present(normalized, job.title):
        return True
    return all_terms_present(normalized, query.title)


def all_terms_present(text: str, value: str) -> bool:
    terms = [term for term in normalize_text(value).split() if len(term) > 1]
    return bool(terms) and all(term in text for term in terms)


def normalize_text(value: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def debug_report_to_markdown(results: list[SourceDebugResult]) -> str:
    lines = ["# Job Link Debug Report", ""]
    for result in results:
        lines.extend([f"## {result.source}", ""])
        for warning in result.warnings:
            lines.append(f"- warning: {escape_md(warning)}")
        if result.warnings:
            lines.append("")
        if not result.jobs:
            lines.extend(["No links found.", ""])
            continue
        lines.extend(
            [
                "| Verdict | Status | Official | Title Found | Job | Company | Final URL |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for debugged in result.jobs:
            job = debugged.job
            verification = debugged.verification
            status = str(verification.status_code or "")
            final_url = verification.final_url or verification.url
            if verification.error:
                status = f"{status} {verification.error}".strip()
            lines.append(
                "| "
                + " | ".join(
                    [
                        escape_md(verification.verdict),
                        escape_md(status),
                        yes_no(verification.official_like),
                        yes_no(verification.title_found),
                        escape_md(job.title),
                        escape_md(job.company),
                        f"[open]({final_url})",
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)


def debug_report_to_flat_markdown(
    results: list[SourceDebugResult],
    title: str,
    per_source_limit: int,
) -> str:
    total_links = sum(len(result.jobs) for result in results)
    lines = [
        "# Job Search Gold Test",
        "",
        f"- Query title: `{escape_md(title)}`",
        "- Location: any",
        f"- Per-source link limit: `{per_source_limit}`",
        f"- Sources tested: `{len(results)}`",
        f"- Links verified: `{total_links}`",
        "",
    ]
    warnings = [
        (result.source, warning) for result in results for warning in result.warnings
    ]
    if warnings:
        lines.extend(["## Source Warnings", ""])
        for source, warning in warnings:
            lines.append(f"- `{escape_md(source)}`: {escape_md(warning)}")
        lines.append("")

    lines.extend(
        [
            "## Concatenated Results",
            "",
            "| Source | Verdict | Status | Official | Title Found | Job | Company | Final Link |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for result in results:
        if not result.jobs:
            lines.append(
                "| "
                + " | ".join(
                    [
                        escape_md(result.source),
                        "no-links",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
                + " |"
            )
            continue
        for debugged in result.jobs:
            job = debugged.job
            verification = debugged.verification
            status = str(verification.status_code or "")
            if verification.error:
                status = f"{status} {verification.error}".strip()
            final_url = verification.final_url or verification.url
            lines.append(
                "| "
                + " | ".join(
                    [
                        escape_md(result.source),
                        escape_md(verification.verdict),
                        escape_md(status),
                        yes_no(verification.official_like),
                        yes_no(verification.title_found),
                        escape_md(job.title),
                        escape_md(job.company),
                        f"[open]({final_url})",
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
