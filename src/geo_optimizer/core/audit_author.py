"""
GEO Audit — Author / E-E-A-T Signals (informational).

Detects byline/authorship signals AI engines weigh as part of Google's
E-E-A-T framework (Experience, Expertise, Authoritativeness, Trust):
a visible author byline, author schema (Person / author property in
JSON-LD), a link to an author bio page, and published/modified dates.
Does not affect the GEO score.
"""

from __future__ import annotations

import re

from geo_optimizer.models.results import AuthorSignalsResult, SchemaResult

_BYLINE_CLASS_RE = re.compile(r"(?:^|[\s_-])(byline|author|written-by|post-author)(?:[\s_-]|$)", re.IGNORECASE)
_BYLINE_TEXT_RE = re.compile(
    r"\b(?:by|written by)\s*:?\s+([A-Z][a-zA-Z.\-']+(?:\s+[A-Z][a-zA-Z.\-']+){0,3})", re.IGNORECASE
)
_AUTHOR_LINK_RE = re.compile(r"/(author|authors|about|team|profile|bio)(?:/|$)", re.IGNORECASE)


def audit_author_signals(soup, schema: SchemaResult | None) -> AuthorSignalsResult:
    """Detect author byline and E-E-A-T signals on a page.

    Args:
        soup: BeautifulSoup of the homepage.
        schema: Parsed JSON-LD schema result (for Person/author detection).

    Returns:
        AuthorSignalsResult with byline, schema, link, and date signals.
    """
    result = AuthorSignalsResult(checked=True)
    if soup is None:
        return result

    _detect_byline(soup, result)
    _detect_author_link(soup, result)
    _detect_author_schema(schema, result)

    if soup.find("time") or soup.find("meta", attrs={"property": "article:published_time"}):
        result.has_published_date = True
        result.signals_found.append("published date")

    result.eeat_score = _score(result)
    return result


def _detect_byline(soup, result: AuthorSignalsResult) -> None:
    meta_author = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", attrs={"property": "article:author"})
    if meta_author and (meta_author.get("content") or "").strip():
        result.has_byline = True
        result.byline_text = meta_author["content"].strip()
        result.signals_found.append("meta[name=author]")
        return

    rel_author = soup.find("a", attrs={"rel": re.compile(r"\bauthor\b", re.IGNORECASE)})
    if rel_author:
        result.has_byline = True
        result.has_author_link = True
        result.byline_text = rel_author.get_text(strip=True)
        result.signals_found.append("rel=author link")
        return

    for el in soup.find_all(class_=_BYLINE_CLASS_RE):
        text = el.get_text(" ", strip=True)
        if text and len(text) < 200:
            result.has_byline = True
            result.byline_text = text
            result.signals_found.append("byline element")
            return

    body = soup.find("body")
    text = body.get_text(" ", strip=True)[:2000] if body else ""
    m = _BYLINE_TEXT_RE.search(text)
    if m:
        result.has_byline = True
        result.byline_text = m.group(1)
        result.signals_found.append("byline text pattern")


def _detect_author_link(soup, result: AuthorSignalsResult) -> None:
    if result.has_author_link:
        return
    for a in soup.find_all("a", href=True):
        if _AUTHOR_LINK_RE.search(a["href"]):
            result.has_author_link = True
            result.signals_found.append("author/about link")
            return


def _detect_author_schema(schema: SchemaResult | None, result: AuthorSignalsResult) -> None:
    if schema is None:
        return
    if schema.has_person:
        result.has_author_schema = True
        result.signals_found.append("Person schema")
    elif any(_has_author_property(s) for s in schema.raw_schemas):
        result.has_author_schema = True
        result.signals_found.append("author property in JSON-LD")
    if schema.has_date_modified:
        result.has_modified_date = True
        result.signals_found.append("dateModified")


def _has_author_property(schema_dict) -> bool:
    if not isinstance(schema_dict, dict):
        return False
    if schema_dict.get("author"):
        return True
    graph = schema_dict.get("@graph")
    if isinstance(graph, list):
        return any(isinstance(node, dict) and node.get("author") for node in graph)
    return False


def _score(result: AuthorSignalsResult) -> int:
    score = 0
    if result.has_byline:
        score += 30
    if result.has_author_schema:
        score += 30
    if result.has_author_link:
        score += 20
    if result.has_published_date:
        score += 10
    if result.has_modified_date:
        score += 10
    return min(score, 100)
