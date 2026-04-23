from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from job_searcher.matching import MatchResult, ProfileMatcher
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
    description: str = ""


@dataclass(frozen=True)
class DebuggedJob:
    job: JobPosting
    verification: LinkVerification


@dataclass(frozen=True)
class SourceDebugResult:
    source: str
    jobs: tuple[DebuggedJob, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class FlatDebugJob:
    source: str
    job: JobPosting
    verification: LinkVerification
    description: str
    match: MatchResult | None
    index: int


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
        description=extract_page_description(text),
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
    description: str = "",
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
        description=description,
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
    profile_matcher: ProfileMatcher | None = None,
    flat_rows: list[FlatDebugJob] | None = None,
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

    rows = sorted_flat_debug_jobs(
        flat_rows if flat_rows is not None else flatten_debug_jobs(results, profile_matcher),
        by_match=bool(profile_matcher),
    )
    lines.extend(["## Concatenated Results", ""])
    header = ["Source", "Verdict", "Status", "Official", "Title Found", "Job", "Company"]
    if profile_matcher:
        header.extend(["Semantic Match", "LLM Match"])
    header.extend(["Description", "Final Link"])
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    no_link_rows = []
    for result in results:
        if not result.jobs:
            no_link_rows.append(
                "| "
                + " | ".join([escape_md(result.source), "no-links", *[""] * (len(header) - 2)])
                + " |"
            )
    for row in rows:
        job = row.job
        verification = row.verification
        status = str(verification.status_code or "")
        if verification.error:
            status = f"{status} {verification.error}".strip()
        final_url = verification.final_url or verification.url
        match_columns: list[str] = []
        if profile_matcher and row.match:
            match_columns = [format_semantic_match(row.match), format_llm_match(row.match)]
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(row.source),
                    escape_md(verification.verdict),
                    escape_md(status),
                    yes_no(verification.official_like),
                    yes_no(verification.title_found),
                    escape_md(job.title),
                    escape_md(job.company),
                    *match_columns,
                    escape_md(row.description),
                    f"[open]({final_url})",
                ]
            )
            + " |"
        )
    lines.extend(no_link_rows)
    lines.append("")
    return "\n".join(lines)


def flatten_debug_jobs(
    results: list[SourceDebugResult],
    profile_matcher: ProfileMatcher | None = None,
) -> list[FlatDebugJob]:
    rows = []
    row_index = 0
    for result in results:
        for debugged in result.jobs:
            job = debugged.job
            verification = debugged.verification
            description = description_for_report(job, verification)
            match = (
                profile_matcher.score(job.title, job.company, description)
                if profile_matcher
                else None
            )
            rows.append(
                FlatDebugJob(
                    source=result.source,
                    job=job,
                    verification=verification,
                    description=description,
                    match=match,
                    index=row_index,
                )
            )
            row_index += 1
    return rows


def sorted_flat_debug_jobs(rows: list[FlatDebugJob], by_match: bool = False) -> list[FlatDebugJob]:
    if not by_match:
        return list(rows)
    return sorted(rows, key=lambda row: (row.match.sort_score if row.match else 0, -row.index), reverse=True)


def format_semantic_match(match: MatchResult) -> str:
    return f"{match.semantic_score:.1f}/100"


def format_llm_match(match: MatchResult) -> str:
    if match.llm_score is None:
        return escape_md(match.llm_error or "not-run")
    if match.llm_reason:
        return escape_md(f"{match.llm_score}/100 - {match.llm_reason}")
    return f"{match.llm_score}/100"


def description_for_report(job: JobPosting, verification: LinkVerification) -> str:
    if job.description:
        return compact_description(html_to_text(job.description))
    return compact_description(verification.description)


def html_to_text(value: str) -> str:
    if "<" not in value or ">" not in value:
        return value
    parser = DescriptionTextParser()
    parser.feed(value)
    return " ".join(parser.chunks)


def compact_description(value: str | None, max_chars: int = 4000) -> str:
    if not value:
        return ""
    compacted = " ".join(value.split())
    if len(compacted) <= max_chars:
        return compacted
    return compacted[: max_chars - 1].rstrip() + "…"


def extract_page_description(html: str) -> str:
    parser = DescriptionTextParser()
    parser.feed(html)
    return compact_description(" ".join(parser.chunks))


class DescriptionTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        elif tag in {"p", "li", "div", "section", "br", "h1", "h2", "h3"} and self.chunks:
            self.chunks.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        value = data.strip()
        if value:
            self.chunks.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
