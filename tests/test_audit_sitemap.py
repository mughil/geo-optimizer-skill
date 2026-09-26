"""Tests for the Sitemap Health check (informational, does not affect GEO score)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from geo_optimizer.core.audit_sitemap import audit_sitemap_health, find_sitemap_url_in_robots


class TestFindSitemapUrlInRobots:
    def test_find_sitemap_url_in_robots_extracts_directive(self):
        text = "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap_index.xml\n"
        assert find_sitemap_url_in_robots(text) == "https://example.com/sitemap_index.xml"

    def test_find_sitemap_url_in_robots_returns_none_when_absent(self):
        text = "User-agent: *\nAllow: /\n"
        assert find_sitemap_url_in_robots(text) is None

    def test_find_sitemap_url_in_robots_returns_none_for_empty_text(self):
        assert find_sitemap_url_in_robots(None) is None
        assert find_sitemap_url_in_robots("") is None


class TestAuditSitemapHealth:
    def test_audit_sitemap_health_no_response_returns_not_found(self):
        result = audit_sitemap_health(r_robots=None, r_sitemap=None, sitemap_url="https://example.com/sitemap.xml")

        assert result.checked is True
        assert result.found is False
        assert any("No sitemap found" in issue for issue in result.issues)

    def test_audit_sitemap_health_404_returns_not_found(self):
        r_sitemap = Mock(status_code=404, text="")

        result = audit_sitemap_health(r_robots=None, r_sitemap=r_sitemap, sitemap_url="https://example.com/sitemap.xml")

        assert result.found is False

    def test_audit_sitemap_health_valid_urlset_computes_url_count(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/</loc><lastmod>2020-01-01</lastmod></url>
            <url><loc>https://example.com/about</loc><lastmod>2020-01-01</lastmod></url>
        </urlset>"""
        r_sitemap = Mock(status_code=200, text=xml)

        result = audit_sitemap_health(r_robots=None, r_sitemap=r_sitemap, sitemap_url="https://example.com/sitemap.xml")

        assert result.found is True
        assert result.is_valid_xml is True
        assert result.is_sitemap_index is False
        assert result.url_count == 2

    def test_audit_sitemap_health_sitemap_index_detected(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
            <sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>
        </sitemapindex>"""
        r_sitemap = Mock(status_code=200, text=xml)

        result = audit_sitemap_health(r_robots=None, r_sitemap=r_sitemap, sitemap_url="https://example.com/sitemap.xml")

        assert result.is_sitemap_index is True
        assert result.url_count == 2

    def test_audit_sitemap_health_invalid_content_flags_issue(self):
        r_sitemap = Mock(status_code=200, text="<html><body>Not a sitemap</body></html>")

        result = audit_sitemap_health(r_robots=None, r_sitemap=r_sitemap, sitemap_url="https://example.com/sitemap.xml")

        assert result.is_valid_xml is False
        assert any("not valid XML" in issue for issue in result.issues)

    def test_audit_sitemap_health_missing_lastmod_flags_issue(self):
        xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/</loc></url>
        </urlset>"""
        r_sitemap = Mock(status_code=200, text=xml)

        result = audit_sitemap_health(r_robots=None, r_sitemap=r_sitemap, sitemap_url="https://example.com/sitemap.xml")

        assert result.has_lastmod is False
        assert any("No <lastmod>" in issue for issue in result.issues)

    def test_audit_sitemap_health_fresh_lastmod_has_zero_stale_ratio(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        xml = f"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/</loc><lastmod>{today}</lastmod></url>
        </urlset>"""
        r_sitemap = Mock(status_code=200, text=xml)

        result = audit_sitemap_health(r_robots=None, r_sitemap=r_sitemap, sitemap_url="https://example.com/sitemap.xml")

        assert result.has_lastmod is True
        assert result.newest_lastmod_days_ago == 0
        assert result.stale_ratio == 0.0

    def test_audit_sitemap_health_old_lastmod_counted_as_stale(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=400)).strftime("%Y-%m-%d")
        xml = f"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/</loc><lastmod>{old_date}</lastmod></url>
        </urlset>"""
        r_sitemap = Mock(status_code=200, text=xml)

        result = audit_sitemap_health(r_robots=None, r_sitemap=r_sitemap, sitemap_url="https://example.com/sitemap.xml")

        assert result.stale_ratio == 1.0

    def test_audit_sitemap_health_referenced_in_robots_true_when_directive_present(self):
        r_robots = Mock(status_code=200, text="Sitemap: https://example.com/sitemap.xml\n")
        xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/</loc><lastmod>2020-01-01</lastmod></url>
        </urlset>"""
        r_sitemap = Mock(status_code=200, text=xml)

        result = audit_sitemap_health(r_robots=r_robots, r_sitemap=r_sitemap, sitemap_url="https://example.com/sitemap.xml")

        assert result.referenced_in_robots is True
        assert not any("not referenced in robots.txt" in issue for issue in result.issues)

    def test_audit_sitemap_health_not_referenced_in_robots_flags_issue(self):
        r_robots = Mock(status_code=200, text="User-agent: *\nAllow: /\n")
        xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/</loc><lastmod>2020-01-01</lastmod></url>
        </urlset>"""
        r_sitemap = Mock(status_code=200, text=xml)

        result = audit_sitemap_health(r_robots=r_robots, r_sitemap=r_sitemap, sitemap_url="https://example.com/sitemap.xml")

        assert result.referenced_in_robots is False
        assert any("not referenced in robots.txt" in issue for issue in result.issues)

    def test_audit_sitemap_health_score_is_zero_when_not_found(self):
        result = audit_sitemap_health(r_robots=None, r_sitemap=None, sitemap_url="https://example.com/sitemap.xml")
        assert result.health_score == 0
