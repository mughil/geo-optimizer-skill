"""
GEO Audit — Sitemap Health (informational).

AI crawlers use /sitemap.xml to discover pages beyond the homepage. A
missing, malformed, or stale sitemap limits how much of the site gets
indexed. Checks presence, XML validity, robots.txt reference, and
<lastmod> freshness. Does not affect the GEO score.

Takes pre-fetched responses (robots.txt + the sitemap URL guess) rather
than fetching on its own, matching the pattern used by robots.txt,
llms.txt, and AI discovery — the caller (``audit.py``) already fetches
these in a single batch and passes the raw responses in.
"""

from __future__ import annotations

from datetime import datetime, timezone

from geo_optimizer.models.results import SitemapHealthResult

_STALE_DAYS = 180


def find_sitemap_url_in_robots(robots_text: str | None) -> str | None:
    """Extract the first `Sitemap:` directive from robots.txt text, if any."""
    if not robots_text:
        return None
    for line in robots_text.splitlines():
        if line.strip().lower().startswith("sitemap:"):
            return line.split(":", 1)[1].strip()
    return None


def audit_sitemap_health(r_robots, r_sitemap, sitemap_url: str) -> SitemapHealthResult:
    """Compute sitemap health from pre-fetched robots.txt and sitemap responses.

    Args:
        r_robots: Pre-fetched robots.txt response (or None).
        r_sitemap: Pre-fetched response for ``sitemap_url`` (or None).
        sitemap_url: The URL that was requested for ``r_sitemap``.

    Returns:
        SitemapHealthResult with discoverability, validity, and freshness signals.
    """
    result = SitemapHealthResult(checked=True)

    robots_text = getattr(r_robots, "text", None) if getattr(r_robots, "status_code", None) == 200 else None
    result.referenced_in_robots = find_sitemap_url_in_robots(robots_text) is not None

    if r_sitemap is None or getattr(r_sitemap, "status_code", None) != 200:
        result.issues.append("No sitemap found at /sitemap.xml or referenced in robots.txt")
        return result

    result.found = True
    result.sitemap_url = sitemap_url

    from bs4 import BeautifulSoup

    try:
        soup = BeautifulSoup(r_sitemap.text, "xml")
    except Exception:
        soup = BeautifulSoup(r_sitemap.text, "html.parser")

    url_tags = soup.find_all("url")
    sitemap_tags = soup.find_all("sitemap")

    if not url_tags and not sitemap_tags:
        result.issues.append("Sitemap is not valid XML or contains no <url>/<sitemap> entries")
        return result

    result.is_valid_xml = True
    result.is_sitemap_index = bool(sitemap_tags) and not url_tags
    entries = url_tags or sitemap_tags
    result.url_count = len(entries)

    _analyze_freshness(entries, result)

    if result.url_count == 0:
        result.issues.append("Sitemap contains no URLs")
    if not result.referenced_in_robots:
        result.issues.append("Sitemap not referenced in robots.txt (add a Sitemap: directive)")

    result.health_score = _score(result)
    return result


def _analyze_freshness(entries, result: SitemapHealthResult) -> None:
    lastmods = [lm.text.strip() for tag in entries if (lm := tag.find("lastmod")) and lm.text]
    if not lastmods:
        result.issues.append("No <lastmod> dates found — AI crawlers can't tell which pages changed recently")
        return

    result.has_lastmod = True
    now = datetime.now(timezone.utc)
    ages_days: list[int] = []
    for raw in lastmods:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ages_days.append((now - dt).days)
        except ValueError:
            continue

    if ages_days:
        result.newest_lastmod_days_ago = min(ages_days)
        stale = sum(1 for a in ages_days if a > _STALE_DAYS)
        result.stale_ratio = round(stale / len(ages_days), 2)


def _score(result: SitemapHealthResult) -> int:
    if not result.found:
        return 0
    if not result.is_valid_xml:
        return 10
    score = 40
    if result.url_count > 0:
        score += 20
    if result.referenced_in_robots:
        score += 20
    if result.has_lastmod:
        score += 10
        if result.stale_ratio < 0.3:
            score += 10
    return min(score, 100)
