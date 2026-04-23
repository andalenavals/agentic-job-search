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
from job_searcher.sources.glassdoor import (
    GlassdoorJobsParser,
    canonicalize_job_url as canonicalize_glassdoor_url,
)
from job_searcher.sources.indeed import (
    IndeedJobsParser,
    canonicalize_job_url as canonicalize_indeed_url,
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
from job_searcher.sources.remotive import matches_query, parse_iso_datetime
from job_searcher.sources.stepstone import (
    StepStoneJobsParser,
    canonicalize_job_url as canonicalize_stepstone_url,
    search_url as stepstone_search_url,
)


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
        self.assertFalse(
            is_likely_official_application("https://www.indeed.com/viewjob?jk=abc123", "Acme")
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
