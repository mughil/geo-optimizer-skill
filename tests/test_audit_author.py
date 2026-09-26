"""Tests for the Author / E-E-A-T Signals check (informational, does not affect GEO score)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from geo_optimizer.core.audit_author import audit_author_signals
from geo_optimizer.models.results import SchemaResult


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


class TestAuditAuthorSignals:
    def test_audit_author_signals_none_soup_returns_unchecked_defaults(self):
        result = audit_author_signals(None, SchemaResult())
        assert result.checked is True
        assert result.has_byline is False
        assert result.eeat_score == 0

    def test_audit_author_signals_meta_author_tag_detected(self):
        soup = _soup('<html><head><meta name="author" content="Jane Doe"></head><body></body></html>')

        result = audit_author_signals(soup, SchemaResult())

        assert result.has_byline is True
        assert result.byline_text == "Jane Doe"
        assert "meta[name=author]" in result.signals_found

    def test_audit_author_signals_rel_author_link_detected(self):
        soup = _soup('<html><body><a rel="author" href="/authors/jane">Jane Doe</a></body></html>')

        result = audit_author_signals(soup, SchemaResult())

        assert result.has_byline is True
        assert result.has_author_link is True
        assert result.byline_text == "Jane Doe"

    def test_audit_author_signals_byline_class_element_detected(self):
        soup = _soup('<html><body><div class="byline">By Jane Doe</div></body></html>')

        result = audit_author_signals(soup, SchemaResult())

        assert result.has_byline is True
        assert "byline element" in result.signals_found

    def test_audit_author_signals_text_pattern_fallback(self):
        soup = _soup("<html><body><p>By Jane Doe, published today.</p></body></html>")

        result = audit_author_signals(soup, SchemaResult())

        assert result.has_byline is True
        assert result.byline_text == "Jane Doe"

    def test_audit_author_signals_no_byline_signals_found(self):
        soup = _soup("<html><body><p>Nothing here about who wrote this.</p></body></html>")

        result = audit_author_signals(soup, SchemaResult())

        assert result.has_byline is False

    def test_audit_author_signals_author_link_detected_anywhere_on_page(self):
        soup = _soup('<html><body><a href="/about/team">Our team</a></body></html>')

        result = audit_author_signals(soup, SchemaResult())

        assert result.has_author_link is True

    def test_audit_author_signals_person_schema_detected(self):
        soup = _soup("<html><body></body></html>")
        schema = SchemaResult(has_person=True)

        result = audit_author_signals(soup, schema)

        assert result.has_author_schema is True
        assert "Person schema" in result.signals_found

    def test_audit_author_signals_author_property_in_raw_schema_detected(self):
        soup = _soup("<html><body></body></html>")
        schema = SchemaResult(raw_schemas=[{"@type": "Article", "author": {"@type": "Person", "name": "Jane"}}])

        result = audit_author_signals(soup, schema)

        assert result.has_author_schema is True
        assert "author property in JSON-LD" in result.signals_found

    def test_audit_author_signals_author_property_in_graph_detected(self):
        soup = _soup("<html><body></body></html>")
        schema = SchemaResult(
            raw_schemas=[{"@graph": [{"@type": "Article", "author": {"@type": "Person", "name": "Jane"}}]}]
        )

        result = audit_author_signals(soup, schema)

        assert result.has_author_schema is True

    def test_audit_author_signals_date_modified_sets_flag(self):
        soup = _soup("<html><body></body></html>")
        schema = SchemaResult(has_date_modified=True)

        result = audit_author_signals(soup, schema)

        assert result.has_modified_date is True

    def test_audit_author_signals_published_date_time_tag_detected(self):
        soup = _soup('<html><body><time datetime="2026-01-01">Jan 1</time></body></html>')

        result = audit_author_signals(soup, SchemaResult())

        assert result.has_published_date is True

    def test_audit_author_signals_full_signals_score_100(self):
        soup = _soup(
            '<html><head><meta name="author" content="Jane Doe"></head>'
            '<body><a href="/about">About</a><time datetime="2026-01-01">Jan 1</time></body></html>'
        )
        schema = SchemaResult(has_person=True, has_date_modified=True)

        result = audit_author_signals(soup, schema)

        assert result.eeat_score == 100
