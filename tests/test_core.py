from __future__ import annotations

import unittest
from datetime import datetime, timezone

from job_searcher.exporters import to_csv, to_markdown
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.official_links import is_likely_official_application
from job_searcher.reporting import SearchReport
from job_searcher.search import collect_jobs
from job_searcher.sources.base import JobSource
from job_searcher.sources.arbeitsagentur import job_detail_url, parse_date
from job_searcher.sources.linkedin import (
    LinkedInJobsParser,
    canonicalize_job_url,
    parse_date as parse_linkedin_date,
)
from job_searcher.sources.remotive import matches_query, parse_iso_datetime


class StaticSource(JobSource):
    name = "static"

    def __init__(self, jobs: list[JobPosting]) -> None:
        self.jobs = jobs

    def search(self, query: SearchQuery, report=None):
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

    def test_rejects_aggregator_links(self) -> None:
        self.assertFalse(
            is_likely_official_application("https://www.linkedin.com/jobs/view/1", "Acme")
        )
        self.assertFalse(
            is_likely_official_application("https://de.linkedin.com/jobs/view/example-1", "Acme")
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
