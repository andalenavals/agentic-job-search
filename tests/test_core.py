from __future__ import annotations

import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from job_searcher.debugging import (
    DebuggedJob,
    FlatDebugJob,
    LinkVerification,
    SourceDebugResult,
    build_verification,
    compact_description,
    content_mentions_job,
    debug_report_to_markdown,
    debug_report_to_flat_markdown,
    debug_sources,
    description_for_report,
    extract_page_description,
    html_to_text,
    source_label,
)
from job_searcher.cli import main as cli_main, normalize_location, normalize_source_names
from job_searcher.emailing import EmailSettings, build_digest_email, select_digest_jobs
from job_searcher.exporters import to_csv, to_markdown
from job_searcher.matching import MatchResult, ProfileMatcher, parse_llm_match_response, semantic_match_score
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.official_links import is_likely_official_application
from job_searcher.reporting import SearchReport
from job_searcher.sources.ashby import (
    ashby_location,
    ashby_url,
    extract_jobs as extract_ashby_jobs,
)
from job_searcher.search import collect_jobs, duplicate_position_key, normalize_position_text, normalize_url
from job_searcher.sources.base import JobSource
from job_searcher.sources.arbeitsagentur import job_detail_url, parse_date
from job_searcher.sources.berlin_startup_jobs import (
    BerlinStartupJobsParser,
    canonicalize_job_url as canonicalize_berlin_startup_jobs_url,
)
from job_searcher.sources.bund_de import (
    BundDeJobsParser,
    canonicalize_job_url as canonicalize_bund_de_url,
    clean_result_title as clean_bund_de_title,
    company_from_result_text as bund_de_company_from_result_text,
    search_url as bund_de_search_url,
)
from job_searcher.sources.experis import (
    ExperisJobsParser,
    canonicalize_job_url as canonicalize_experis_url,
    search_url as experis_search_url,
)
from job_searcher.sources.glassdoor import (
    GlassdoorJobsParser,
    canonicalize_job_url as canonicalize_glassdoor_url,
)
from job_searcher.sources.google import (
    build_google_query,
    clean_title as clean_google_title,
    company_from_url as google_company_from_url,
)
from job_searcher.sources.indeed import (
    IndeedJobsParser,
    canonicalize_job_url as canonicalize_indeed_url,
)
from job_searcher.sources.interamt import InteramtJobsParser, is_job_href as interamt_is_job_href
from job_searcher.sources.karriere_nrw import (
    matches_query as karriere_nrw_matches_query,
    public_job_url as karriere_nrw_public_job_url,
)
from job_searcher.sources.kununu import (
    canonicalize_job_url as canonicalize_kununu_url,
    extract_jobs as extract_kununu_jobs,
    parse_date as parse_kununu_date,
    public_job_url as kununu_public_job_url,
    search_url as kununu_search_url,
)
from job_searcher.sources.linkedin import (
    LinkedInJobsParser,
    canonicalize_job_url,
    parse_date as parse_linkedin_date,
)
from job_searcher.sources.personio import parse_positions, personio_url, text_value
from job_searcher.sources.remote_com import (
    extract_jobs as extract_remote_com_jobs,
    search_url as remote_com_search_url,
)
from job_searcher.sources.remotive import matches_query, parse_iso_datetime
from job_searcher.sources.smartrecruiters import (
    extract_postings as extract_smartrecruiters_postings,
    location_name as smartrecruiters_location_name,
)
from job_searcher.sources.stepstone import (
    StepStoneJobsParser,
    canonicalize_job_url as canonicalize_stepstone_url,
    search_url as stepstone_search_url,
)
from job_searcher.sources.workday import (
    WorkdayJobsParser,
    canonicalize_job_url as canonicalize_workday_url,
)
from job_searcher.sources.xing import (
    XingJobsParser,
    canonicalize_job_url as canonicalize_xing_url,
    is_job_href as xing_is_job_href,
    is_navigation_title as xing_is_navigation_title,
    search_url as xing_search_url,
)


class StaticSource(JobSource):
    name = "static"

    def __init__(self, jobs: list[JobPosting]) -> None:
        self.jobs = jobs

    def search(self, query: SearchQuery, report=None):
        return self.jobs


class CountingSource(JobSource):
    def __init__(self, name: str, jobs: list[JobPosting], calls: list[str]) -> None:
        self.name = name
        self.jobs = jobs
        self.calls = calls

    def search(self, query: SearchQuery, report=None):
        self.calls.append(self.name)
        return self.jobs


class OfficialLinkTests(unittest.TestCase):
    def test_recognizes_known_ats_links(self) -> None:
        self.assertTrue(
            is_likely_official_application("https://boards.greenhouse.io/acme/jobs/1", "Acme")
        )
        self.assertTrue(is_likely_official_application("https://jobs.lever.co/acme/1", "Acme"))
        self.assertTrue(
            is_likely_official_application(
                "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1-S", "Acme"
            )
        )
        self.assertTrue(
            is_likely_official_application(
                "https://www.karriere.nrw/stellenausschreibung/abc123", "Acme"
            )
        )
        self.assertTrue(
            is_likely_official_application(
                "https://jobs.ashbyhq.com/acme/abc123",
                "Acme",
            )
        )
        self.assertTrue(
            is_likely_official_application(
                "https://acme.jobs.personio.de/job/123",
                "Acme",
            )
        )
        self.assertTrue(
            is_likely_official_application(
                "https://careers.smartrecruiters.com/Acme/data-analyst",
                "Acme",
            )
        )
        self.assertTrue(
            is_likely_official_application(
                "https://acme.wd1.myworkdayjobs.com/en-US/careers/job/Data-Analyst",
                "Acme",
            )
        )
        self.assertTrue(
            is_likely_official_application(
                "https://www.service.bund.de/Content/DE/Stellenangebote/abc.html",
                "Bund",
            )
        )

    def test_rejects_aggregator_links(self) -> None:
        self.assertFalse(
            is_likely_official_application("https://www.linkedin.com/jobs/view/1", "Acme")
        )
        self.assertFalse(
            is_likely_official_application("https://de.linkedin.com/jobs/view/example-1", "Acme")
        )
        self.assertFalse(
            is_likely_official_application("https://www.indeed.com/viewjob?jk=abc123", "Acme")
        )
        self.assertFalse(
            is_likely_official_application(
                "https://www.experis.de/de/job/it/data-analyst/abc123",
                "Acme",
            )
        )
        self.assertFalse(
            is_likely_official_application(
                "https://www.glassdoor.de/job-listing/data-analyst-acme-JV.htm?jl=123",
                "Acme",
            )
        )
        self.assertFalse(
            is_likely_official_application(
                "https://www.kununu.com/job-postings/de/abc123",
                "Acme",
            )
        )
        self.assertFalse(
            is_likely_official_application(
                "https://www.stepstone.de/stellenangebote--data-analyst-berlin--123.html",
                "Acme",
            )
        )
        self.assertFalse(
            is_likely_official_application(
                "https://berlinstartupjobs.com/jobs/data-analyst-acme",
                "Acme",
            )
        )
        self.assertFalse(
            is_likely_official_application("https://www.xing.com/jobs/berlin-data-analyst-1")
        )


class SearchTests(unittest.TestCase):
    def test_filters_unverified_links_by_default(self) -> None:
        jobs = [
            JobPosting("Engineer", "Acme", "Berlin", "test", "https://linkedin.com/jobs/view/1"),
            JobPosting("Engineer", "Acme", "Berlin", "test", "https://jobs.lever.co/acme/1"),
        ]
        report = SearchReport()
        results = collect_jobs([StaticSource(jobs)], SearchQuery(title="Engineer"), report)
        self.assertEqual([job.best_url for job in results], ["https://jobs.lever.co/acme/1"])
        self.assertEqual(report.seen, 2)
        self.assertEqual(report.accepted, 1)
        self.assertEqual(report.filtered_unverified, 1)

    def test_can_include_unverified_links(self) -> None:
        jobs = [
            JobPosting("Engineer", "Acme", "Berlin", "test", "https://linkedin.com/jobs/view/1")
        ]
        results = collect_jobs(
            [StaticSource(jobs)], SearchQuery(title="Engineer", include_unverified=True)
        )
        self.assertEqual(len(results), 1)

    def test_filters_duplicate_links(self) -> None:
        jobs = [
            JobPosting("Engineer", "Acme", "Berlin", "a", "https://jobs.lever.co/acme/1"),
            JobPosting("Engineer II", "Acme", "Berlin", "b", "https://jobs.lever.co/acme/1/"),
        ]
        report = SearchReport()
        results = collect_jobs([StaticSource(jobs)], SearchQuery(title="Engineer"), report)
        self.assertEqual(len(results), 1)
        self.assertEqual(report.filtered_duplicate_links, 1)
        self.assertEqual(report.filtered_duplicates, 1)

    def test_filters_duplicate_positions_with_different_links(self) -> None:
        jobs = [
            JobPosting("Data Analyst", "Acme GmbH", "Berlin", "agentur", "https://jobs.lever.co/acme/1"),
            JobPosting("Data Analyst", "Acme GmbH", "Berlin", "linkedin", "https://jobs.lever.co/acme/2"),
            JobPosting("Data Analyst", "Acme GmbH", "Munich", "linkedin", "https://jobs.lever.co/acme/3"),
        ]
        report = SearchReport()
        results = collect_jobs([StaticSource(jobs)], SearchQuery(title="Data Analyst"), report)
        self.assertEqual([job.best_url for job in results], [
            "https://jobs.lever.co/acme/1",
            "https://jobs.lever.co/acme/3",
        ])
        self.assertEqual(report.filtered_duplicate_positions, 1)
        self.assertEqual(report.filtered_duplicates, 1)

    def test_does_not_position_dedupe_when_company_is_missing(self) -> None:
        jobs = [
            JobPosting("Data Analyst", "", "Berlin", "a", "https://jobs.lever.co/acme/1"),
            JobPosting("Data Analyst", "", "Berlin", "b", "https://jobs.lever.co/acme/2"),
        ]
        results = collect_jobs([StaticSource(jobs)], SearchQuery(title="Data Analyst"))
        self.assertEqual(len(results), 2)

    def test_duplicate_key_helpers(self) -> None:
        job = JobPosting(
            "  Senior Data-Analyst ",
            "ACME GmbH",
            "Berlin, Germany",
            "test",
            "https://jobs.lever.co/acme/1/",
        )
        self.assertEqual(normalize_position_text("Senior Data-Analyst"), "senior data analyst")
        self.assertEqual(normalize_url(job.best_url), "https://jobs.lever.co/acme/1")
        self.assertEqual(
            duplicate_position_key(job),
            ("senior data analyst", "acme gmbh", "berlin germany"),
        )

    def test_sorts_newest_first(self) -> None:
        older = JobPosting(
            "Engineer",
            "Beta",
            "Berlin",
            "test",
            "https://jobs.lever.co/beta/1",
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        newer = JobPosting(
            "Engineer",
            "Acme",
            "Berlin",
            "test",
            "https://jobs.lever.co/acme/1",
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        results = collect_jobs([StaticSource([older, newer])], SearchQuery(title="Engineer"))
        self.assertEqual([job.company for job in results], ["Acme", "Beta"])

    def test_queries_all_sources_before_applying_limit(self) -> None:
        calls: list[str] = []
        first = CountingSource(
            "first",
            [JobPosting("Engineer", "Acme", "Berlin", "test", "https://jobs.lever.co/acme/1")],
            calls,
        )
        second = CountingSource(
            "second",
            [JobPosting("Engineer", "Beta", "Berlin", "test", "https://jobs.lever.co/beta/1")],
            calls,
        )
        results = collect_jobs([first, second], SearchQuery(title="Engineer", limit=1))
        self.assertEqual(calls, ["first", "second"])
        self.assertEqual(len(results), 1)


class CliTests(unittest.TestCase):
    def test_source_all_expands_to_every_selectable_source(self) -> None:
        sources = normalize_source_names(["all"])
        self.assertIn("agentur", sources)
        self.assertIn("google", sources)
        self.assertIn("instaffo", sources)

    def test_source_all_overrides_other_source_names(self) -> None:
        sources = normalize_source_names(["linkedin", "all"])
        self.assertIn("agentur", sources)
        self.assertIn("instaffo", sources)

    def test_default_sources_do_not_include_configured_google_or_placeholder(self) -> None:
        sources = normalize_source_names(None)
        self.assertIn("agentur", sources)
        self.assertNotIn("google", sources)
        self.assertNotIn("instaffo", sources)

    def test_location_all_means_no_location_filter(self) -> None:
        self.assertIsNone(normalize_location("all"))
        self.assertIsNone(normalize_location(" ALL "))
        self.assertEqual(normalize_location("Berlin"), "Berlin")

    def test_debug_report_still_writes_when_email_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            stderr = io.StringIO()
            with (
                patch("job_searcher.cli.build_sources", return_value=[]),
                patch(
                    "job_searcher.cli.email_settings_from_env",
                    return_value=EmailSettings(
                        host="smtp.example.com",
                        port=587,
                        from_addr="from@example.com",
                    ),
                ),
                patch("job_searcher.cli.send_email", side_effect=RuntimeError("smtp down")),
                patch("sys.stderr", new=stderr),
            ):
                exit_code = cli_main(
                    [
                        "--title",
                        "Data",
                        "--source",
                        "all",
                        "--location",
                        "all",
                        "--debug-links",
                        "--include-unverified",
                        "--email-to",
                        "to@example.com",
                        "--output",
                        str(output_path),
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())
            self.assertIn("# Job Link Debug Report", output_path.read_text(encoding="utf-8"))
            self.assertIn("warning: could not send email to to@example.com", stderr.getvalue())
            self.assertIn("The report was still produced.", stderr.getvalue())


class DebuggingTests(unittest.TestCase):
    def test_debug_sources_verifies_each_source_limit(self) -> None:
        jobs = [
            JobPosting("Data Analyst", "Acme", "Berlin", "test", "https://jobs.lever.co/acme/1"),
            JobPosting("Data Engineer", "Acme", "Berlin", "test", "https://jobs.lever.co/acme/2"),
        ]

        def fake_verifier(job: JobPosting, query: SearchQuery, timeout: int) -> LinkVerification:
            return build_verification(
                url=job.best_url,
                final_url=job.best_url,
                reachable=True,
                status_code=200,
                content_type="text/html",
                official_like=True,
                title_found=True,
            )

        results = debug_sources(
            [StaticSource(jobs)],
            SearchQuery(title="data analyst", include_unverified=True),
            per_source_limit=1,
            verifier=fake_verifier,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "static")
        self.assertEqual(len(results[0].jobs), 1)
        self.assertEqual(results[0].jobs[0].verification.verdict, "verified")

    def test_source_label_includes_company_token(self) -> None:
        source = StaticSource([])
        source.company_token = "acme"
        self.assertEqual(source_label(source), "static:acme")

    def test_debug_report_markdown(self) -> None:
        job = JobPosting("Data Analyst", "Acme", "Berlin", "test", "https://jobs.lever.co/acme/1")
        verification = build_verification(
            url=job.best_url,
            final_url=job.best_url,
            reachable=True,
            status_code=200,
            content_type="text/html",
            official_like=True,
            title_found=True,
        )
        report = debug_report_to_markdown(
            [
                SourceDebugResult(
                    source="test",
                    warnings=(),
                    jobs=(DebuggedJob(job=job, verification=verification),),
                )
            ]
        )
        self.assertIn("## test", report)
        self.assertIn("verified", report)
        self.assertIn("[open](https://jobs.lever.co/acme/1)", report)

    def test_flat_debug_report_markdown(self) -> None:
        job = JobPosting(
            "Data Analyst",
            "Acme",
            "Berlin",
            "test",
            "https://jobs.lever.co/acme/1",
            description="Analyze customer data and build dashboards.",
        )
        verification = build_verification(
            url=job.best_url,
            final_url=job.best_url,
            reachable=True,
            status_code=200,
            content_type="text/html",
            official_like=True,
            title_found=True,
        )
        report = debug_report_to_flat_markdown(
            [
                SourceDebugResult(
                    source="test",
                    warnings=(),
                    jobs=(DebuggedJob(job=job, verification=verification),),
                )
            ],
            title="Data",
            per_source_limit=5,
        )
        self.assertIn("# Job Search Gold Test", report)
        self.assertIn(
            "| test | verified | 200 | yes | yes | Data Analyst | Acme | "
            "Analyze customer data and build dashboards. |",
            report,
        )
        self.assertIn(
            "| Source | Verdict | Status | Official | Title Found | Job | Company | Description | Final Link |",
            report,
        )

    def test_flat_debug_report_sorts_by_profile_match(self) -> None:
        python_job = JobPosting(
            "Data Engineer",
            "Acme",
            "Berlin",
            "test",
            "https://jobs.lever.co/acme/1",
            description="Build Python SQL data pipelines and analytics models.",
        )
        sales_job = JobPosting(
            "Sales Manager",
            "Beta",
            "Berlin",
            "test",
            "https://jobs.lever.co/beta/1",
            description="Lead enterprise sales calls and account planning.",
        )
        verification = build_verification(
            "https://x",
            "https://x",
            True,
            200,
            "text/html",
            True,
            True,
        )
        report = debug_report_to_flat_markdown(
            [
                SourceDebugResult(
                    source="test",
                    warnings=(),
                    jobs=(
                        DebuggedJob(job=sales_job, verification=verification),
                        DebuggedJob(job=python_job, verification=verification),
                    ),
                )
            ],
            title="Data",
            per_source_limit=5,
            profile_matcher=ProfileMatcher(
                "Data engineer with Python, SQL, analytics, and machine learning experience.",
                ollama_model=None,
            ),
        )
        self.assertIn(
            "| Source | Verdict | Status | Official | Title Found | Job | Company | Semantic Match | LLM Match | Description | Final Link |",
            report,
        )
        self.assertLess(report.index("Data Engineer"), report.index("Sales Manager"))
        self.assertIn("not-run", report)

    def test_description_helpers(self) -> None:
        html = """
        <html>
          <head><style>.hidden{}</style><script>ignored()</script></head>
          <body>
            <h1>Data Analyst</h1>
            <p>Analyze customer data.</p>
            <li>Build dashboards.</li>
          </body>
        </html>
        """
        self.assertEqual(
            extract_page_description(html),
            "Data Analyst Analyze customer data. Build dashboards.",
        )
        verification = build_verification(
            "https://x",
            "https://x",
            True,
            200,
            "text/html",
            True,
            True,
            description="Fetched page description",
        )
        job = JobPosting("Data Analyst", "Acme", "Berlin", "test", "https://x")
        self.assertEqual(description_for_report(job, verification), "Fetched page description")
        described_job = JobPosting(
            "Data Analyst",
            "Acme",
            "Berlin",
            "test",
            "https://x",
            description="Source description",
        )
        self.assertEqual(description_for_report(described_job, verification), "Source description")
        self.assertEqual(compact_description("x" * 10, max_chars=5), "xxxx…")
        self.assertEqual(html_to_text("<p>Hello <strong>Data</strong></p>"), "Hello Data")

    def test_matching_helpers(self) -> None:
        self.assertGreater(
            semantic_match_score(
                "Python SQL data analyst",
                "Data analyst role using Python and SQL dashboards.",
            ),
            semantic_match_score("Python SQL data analyst", "Retail store manager."),
        )
        self.assertEqual(
            parse_llm_match_response('<think>hidden</think>{"score": 88, "reason": "Strong data fit"}'),
            (88, "Strong data fit", ""),
        )

    def test_email_digest_selects_top_jobs(self) -> None:
        verification = build_verification(
            "https://jobs.example/1",
            "https://jobs.example/1",
            True,
            200,
            "text/html",
            True,
            True,
        )
        weak = FlatDebugJob(
            source="source-a",
            job=JobPosting("Sales Manager", "Beta", "Berlin", "test", "https://jobs.example/1"),
            verification=verification,
            description="Sales role",
            match=MatchResult(semantic_score=10, llm_score=20),
            index=0,
        )
        strong = FlatDebugJob(
            source="source-b",
            job=JobPosting(
                "Data Analyst",
                "Acme",
                "Berlin",
                "test",
                "https://jobs.example/2",
                published_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            ),
            verification=verification,
            description="Python SQL dashboards",
            match=MatchResult(semantic_score=80, llm_score=90, llm_reason="Strong fit"),
            index=1,
        )
        self.assertEqual(select_digest_jobs([weak, strong], limit=1, sort_by="match"), [strong])
        self.assertEqual(select_digest_jobs([weak, strong], limit=1, sort_by="newest"), [strong])
        message = build_digest_email(
            [weak, strong],
            query_title="Data",
            to_addr="to@example.com",
            from_addr="from@example.com",
            limit=1,
            sort_by="match",
        )
        body = message.get_content()
        self.assertIn("# Top job links for: Data", body)
        self.assertIn("https://jobs.example/1", body)
        self.assertNotIn("Sales Manager", body)

    def test_verification_verdicts(self) -> None:
        self.assertEqual(
            build_verification("https://x", "https://x", False, 404, "", False, False).verdict,
            "missing",
        )
        self.assertEqual(
            build_verification("https://x", "https://x", True, 200, "", True, True).verdict,
            "verified",
        )
        self.assertEqual(
            build_verification("https://x", "https://x", True, 200, "", False, False).verdict,
            "suspicious",
        )

    def test_content_mentions_job(self) -> None:
        job = JobPosting("Senior Data Analyst", "Acme", "Berlin", "test", "https://jobs/acme")
        self.assertTrue(content_mentions_job("Join us as a Senior Data Analyst.", job, SearchQuery("data analyst")))
        self.assertFalse(content_mentions_job("Join us as a Product Manager.", job, SearchQuery("data analyst")))


class ExportTests(unittest.TestCase):
    def test_exports_markdown_and_csv(self) -> None:
        jobs = [JobPosting("Engineer", "Acme", "Berlin", "test", "https://jobs.lever.co/acme/1")]
        self.assertIn("[Apply](https://jobs.lever.co/acme/1)", to_markdown(jobs))
        self.assertIn("Engineer,Acme,Berlin,test", to_csv(jobs))


class SourceMatchingTests(unittest.TestCase):
    def test_arbeitsagentur_helpers(self) -> None:
        self.assertEqual(
            job_detail_url("10001-1002774853-S"),
            "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1002774853-S",
        )
        parsed = parse_date("2026-03-17")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)

    def test_linkedin_card_parser(self) -> None:
        parser = LinkedInJobsParser()
        parser.feed(
            """
            <div class="base-card job-search-card">
              <a class="base-card__full-link" href="https://de.linkedin.com/jobs/view/x-123?position=1&amp;pageNum=0">
                <span class="sr-only">Ignored</span>
              </a>
              <h3 class="base-search-card__title">Data Analyst</h3>
              <h4 class="base-search-card__subtitle">
                <a class="hidden-nested-link">Acme GmbH</a>
              </h4>
              <span class="job-search-card__location">Berlin, Germany</span>
              <time class="job-search-card__listdate" datetime="2026-04-22">today</time>
            </div>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Data Analyst")
        self.assertEqual(parser.cards[0].company, "Acme GmbH")
        self.assertEqual(parser.cards[0].location, "Berlin, Germany")
        self.assertEqual(
            canonicalize_job_url(parser.cards[0].url),
            "https://de.linkedin.com/jobs/view/x-123",
        )
        parsed = parse_linkedin_date(parser.cards[0].published_at)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)

    def test_indeed_card_parser(self) -> None:
        parser = IndeedJobsParser()
        parser.feed(
            """
            <div class="cardOutline result job_abc123">
              <h2 class="jobTitle">
                <a class="jcs-JobTitle" data-jk="abc123" href="/rc/clk?jk=abc123&amp;from=serp">
                  <span title="Data Analyst" id="jobTitle-abc123">Data Analyst</span>
                </a>
              </h2>
              <span data-testid="company-name">Acme GmbH</span>
              <div data-testid="text-location">Berlin</div>
            </div>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Data Analyst")
        self.assertEqual(parser.cards[0].company, "Acme GmbH")
        self.assertEqual(parser.cards[0].location, "Berlin")
        self.assertEqual(
            canonicalize_indeed_url(parser.cards[0].url),
            "https://www.indeed.com/viewjob?jk=abc123",
        )

    def test_glassdoor_card_parser(self) -> None:
        parser = GlassdoorJobsParser()
        parser.feed(
            """
            <li data-test="jobListing">
              <a data-test="job-link" href="/job-listing/data-analyst-acme-JV.htm?jl=123">
                <span data-test="job-title">
                  <style>.noise{color:red}</style>
                  Data Analyst
                </span>
              </a>
              <div data-test="employer-name">Acme GmbH</div>
              <span data-test="emp-location">Berlin</span>
            </li>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Data Analyst")
        self.assertEqual(parser.cards[0].company, "Acme GmbH")
        self.assertEqual(parser.cards[0].location, "Berlin")
        self.assertEqual(
            canonicalize_glassdoor_url(parser.cards[0].url),
            "https://www.glassdoor.de/job-listing/data-analyst-acme-JV.htm?jl=123",
        )

    def test_google_query_helpers(self) -> None:
        query = build_google_query(SearchQuery(title="data analyst", location="Berlin"))
        self.assertIn("data analyst", query)
        self.assertIn("Berlin", query)
        self.assertIn("-site:linkedin.com", query)
        self.assertEqual(clean_google_title("Data Analyst | Acme Careers"), "Data Analyst")
        self.assertEqual(google_company_from_url("https://jobs.lever.co/acme/abc"), "lever")

    def test_berlin_startup_jobs_parser(self) -> None:
        parser = BerlinStartupJobsParser()
        parser.feed(
            """
            <article>
              <a href="/jobs/data-analyst-acme/">Data Analyst</a>
              <span class="company">Acme GmbH</span>
              <span class="location">Berlin</span>
            </article>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Data Analyst")
        self.assertEqual(parser.cards[0].company, "Acme GmbH")
        self.assertEqual(parser.cards[0].location, "Berlin")
        self.assertEqual(
            canonicalize_berlin_startup_jobs_url(parser.cards[0].url),
            "https://berlinstartupjobs.com/jobs/data-analyst-acme/",
        )

    def test_xing_parser_and_url(self) -> None:
        parser = XingJobsParser()
        parser.feed(
            """
            <a href="/jobs/search/ki">Suche</a>
            <a href="/jobs/directory/a">Jobs Verzeichnis</a>
            <a href="/jobs/berlin-data-analyst-123">Data Analyst</a>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Data Analyst")
        self.assertEqual(
            canonicalize_xing_url(parser.cards[0].url),
            "https://www.xing.com/jobs/berlin-data-analyst-123",
        )
        self.assertEqual(
            xing_search_url(SearchQuery(title="data analyst", location="Berlin")),
            "https://www.xing.com/jobs/berlin-data-analyst",
        )
        self.assertTrue(xing_is_job_href("/jobs/berlin-data-analyst-123"))
        self.assertFalse(xing_is_job_href("/jobs/search/ki"))
        self.assertTrue(xing_is_navigation_title("Job posten"))

    def test_bund_de_parser(self) -> None:
        parser = BundDeJobsParser()
        parser.feed(
            """
            <a href="IMPORTE/Stellenangebote/editor/example/abc.html;jsessionid=123?templateQueryString=Data">
              Data Analyst im Bundesdienst
            </a>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Data Analyst im Bundesdienst")
        self.assertEqual(
            parser.cards[0].url,
            "https://www.service.bund.de/IMPORTE/Stellenangebote/editor/example/abc.html;jsessionid=123?templateQueryString=Data",
        )
        self.assertEqual(
            canonicalize_bund_de_url(parser.cards[0].url),
            "https://www.service.bund.de/IMPORTE/Stellenangebote/editor/example/abc.html",
        )
        self.assertEqual(
            bund_de_search_url(SearchQuery(title="Data")),
            "https://www.service.bund.de/Content/DE/Stellen/Suche/Formular.html?nn=4642046&type=0&searchResult=true&templateQueryString=Data",
        )
        raw_title = (
            "Stellenbezeichnung Data Scientist Arbeitgeber Bundesamt "
            "Veröffentlicht 23.04.26 Bewerbungsfrist 24.05.26"
        )
        self.assertEqual(clean_bund_de_title(raw_title), "Data Scientist")
        self.assertEqual(bund_de_company_from_result_text(raw_title), "Bundesamt")

    def test_interamt_parser(self) -> None:
        parser = InteramtJobsParser()
        parser.feed(
            """
            <a href="./stellensuche?0">Stellensuche</a>
            <a href="/cms/Hilfe/200_Hilfe_Stellensuche_Suchmaske.html">Hilfe</a>
            <a href="./stellenangebot/123">Data Scientist</a>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Data Scientist")
        self.assertEqual(
            parser.cards[0].url,
            "https://interamt.de/stellenangebot/123",
        )
        self.assertTrue(interamt_is_job_href("./stellenangebot/123"))
        self.assertFalse(interamt_is_job_href("./stellensuche?0"))

    def test_ashby_helpers(self) -> None:
        payload = {
            "jobs": [
                {
                    "title": "Data Analyst",
                    "location": {"name": "Berlin"},
                    "jobUrl": "https://jobs.ashbyhq.com/acme/abc123",
                }
            ]
        }
        jobs = extract_ashby_jobs(payload)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(ashby_location(jobs[0]), "Berlin")
        self.assertEqual(ashby_url(jobs[0]), "https://jobs.ashbyhq.com/acme/abc123")

    def test_smartrecruiters_helpers(self) -> None:
        payload = {
            "content": [
                {
                    "name": "Data Analyst",
                    "location": {"city": "Berlin", "country": "Germany"},
                    "ref": "https://jobs.smartrecruiters.com/Acme/123-data-analyst",
                }
            ]
        }
        postings = extract_smartrecruiters_postings(payload)
        self.assertEqual(len(postings), 1)
        self.assertEqual(smartrecruiters_location_name(postings[0]), "Berlin, Germany")

    def test_personio_helpers(self) -> None:
        xml = """
        <workzag-jobs>
          <position>
            <id>123</id>
            <name>Data Analyst</name>
            <office>Berlin</office>
          </position>
        </workzag-jobs>
        """
        positions = parse_positions(xml)
        self.assertEqual(len(positions), 1)
        self.assertEqual(text_value(positions[0], "name"), "Data Analyst")
        self.assertEqual(personio_url("acme", "123"), "https://acme.jobs.personio.de/job/123")

    def test_workday_parser(self) -> None:
        parser = WorkdayJobsParser("https://acme.wd1.myworkdayjobs.com/careers")
        parser.feed(
            """
            <a href="/careers/job/Berlin/Data-Analyst_R123">
              Data Analyst
            </a>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Data Analyst")
        self.assertEqual(
            canonicalize_workday_url(parser.cards[0].url),
            "https://acme.wd1.myworkdayjobs.com/careers/job/Berlin/Data-Analyst_R123",
        )

    def test_experis_card_parser(self) -> None:
        parser = ExperisJobsParser()
        parser.feed(
            """
            <div class="job-search-result card">
              <div class="card-body">
                <div class="job-actionbar"><div class="date">19/04/2026</div></div>
                <div class="job-position">
                  <h2 class="title">
                    <a href="/de/job/it/data-analyst/abc123">Data Analyst</a>
                  </h2>
                </div>
                <div class="job-details">
                  <div class="location"><img alt="location icon"/>Berlin</div>
                </div>
              </div>
            </div>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Data Analyst")
        self.assertEqual(parser.cards[0].location, "Berlin")
        self.assertEqual(
            canonicalize_experis_url(parser.cards[0].url),
            "https://www.experis.de/de/job/it/data-analyst/abc123",
        )
        self.assertEqual(
            experis_search_url(SearchQuery(title="data analyst")),
            "https://www.experis.de/de/search/beruf/data-analyst",
        )

    def test_karriere_nrw_helpers(self) -> None:
        item = {
            "uuid": "abc123",
            "titel_der_stelle": "Data Analyst",
            "ausschreibende_behoerde": "Land NRW",
            "ort": "Düsseldorf",
        }
        self.assertTrue(karriere_nrw_matches_query(item, SearchQuery("data analyst")))
        self.assertFalse(
            karriere_nrw_matches_query(item, SearchQuery("data analyst", location="Berlin"))
        )
        self.assertEqual(
            karriere_nrw_public_job_url("abc123"),
            "https://www.karriere.nrw/stellenausschreibung/abc123",
        )

    def test_kununu_next_data_parser(self) -> None:
        html = """
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "searchJobs": {
                "jobs": [
                  {
                    "id": "abc123",
                    "title": "Data Analyst",
                    "city": "Berlin",
                    "region": "Berlin",
                    "url": "/job-postings/de/abc123",
                    "postedAt": "2026-04-20",
                    "profile": {"companyName": "Acme GmbH"}
                  }
                ]
              }
            }
          }
        }
        </script>
        """
        jobs = extract_kununu_jobs(html)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Data Analyst")
        self.assertEqual(
            kununu_public_job_url(jobs[0]),
            "https://www.kununu.com/de/job/abc123",
        )
        self.assertEqual(
            canonicalize_kununu_url("https://www.kununu.com/de/job/abc123?foo=bar"),
            "https://www.kununu.com/de/job/abc123",
        )
        parsed = parse_kununu_date(jobs[0]["postedAt"])
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(
            kununu_search_url(SearchQuery(title="data analyst", location="Berlin")),
            "https://www.kununu.com/de/jobs/j-data-analyst/l-state-berlin",
        )

    def test_remote_com_jobs_data_parser(self) -> None:
        html = (
            '<script>self.__next_f.push([1,"'
            '\\"jobsData\\":{\\"jobs\\":[{\\"title\\":\\"Data Analyst\\",'
            '\\"slug\\":\\"data-analyst-j1\\",'
            '\\"applyUrl\\":\\"https://jobs.lever.co/acme/abc\\",'
            '\\"publishedAt\\":\\"2026-04-17T21:03:05Z\\",'
            '\\"companyProfile\\":{\\"name\\":\\"Acme\\"},'
            '\\"hiringLocation\\":{\\"includedLocations\\":[{\\"value\\":{\\"name\\":\\"Germany\\"}}]}}]}}'
            '"])</script>'
        )
        jobs = extract_remote_com_jobs(html)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Data Analyst")
        self.assertEqual(jobs[0]["applyUrl"], "https://jobs.lever.co/acme/abc")
        self.assertEqual(
            remote_com_search_url(SearchQuery(title="data analyst")),
            "https://remote.com/jobs/types-of-remote-jobs/remote-data-analyst-jobs",
        )
        with self.assertRaisesRegex(ValueError, "Could not find Remote.com jobsData payload"):
            extract_remote_com_jobs("<html>No embedded jobs</html>")

    def test_stepstone_card_parser(self) -> None:
        parser = StepStoneJobsParser()
        parser.feed(
            """
            <article data-at="job-item" data-testid="job-item">
              <a data-at="job-item-title" href="/stellenangebote--Senior-Data-Analyst-Berlin-Acme--123-inline.html">
                <style>.noise{color:red}</style>
                <div><div>Senior Data Analyst</div></div>
              </a>
              <span data-at="job-item-company-name">
                <span><svg><path></path></svg></span>
                <span>Acme GmbH</span>
              </span>
              <span data-at="job-item-location">
                <span><svg><path></path></svg></span>
                <span>Berlin</span>
              </span>
            </article>
            """
        )
        self.assertEqual(len(parser.cards), 1)
        self.assertEqual(parser.cards[0].title, "Senior Data Analyst")
        self.assertEqual(parser.cards[0].company, "Acme GmbH")
        self.assertEqual(parser.cards[0].location, "Berlin")
        self.assertEqual(
            canonicalize_stepstone_url(parser.cards[0].url),
            "https://www.stepstone.de/stellenangebote--Senior-Data-Analyst-Berlin-Acme--123-inline.html",
        )
        self.assertEqual(
            stepstone_search_url(SearchQuery(title="data analyst", location="Berlin")),
            "https://www.stepstone.de/jobs/data-analyst/in-berlin",
        )

    def test_remotive_match_requires_all_title_terms(self) -> None:
        query = SearchQuery(title="ai engineer")
        self.assertTrue(matches_query("Senior AI Engineer", "Acme", query))
        self.assertFalse(matches_query("Customer Support", "Acme", query))

    def test_remotive_iso_dates_parse(self) -> None:
        parsed = parse_iso_datetime("2026-04-22T10:30:00Z")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)


if __name__ == "__main__":
    unittest.main()
