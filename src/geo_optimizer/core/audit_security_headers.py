"""
GEO Audit — Security Response Headers (informational).

Checks standard HTTP security headers (HSTS, CSP, X-Content-Type-Options,
Referrer-Policy, Permissions-Policy, X-Frame-Options). These don't block
AI crawlers directly, but a well-maintained site with modern security
headers is a light-weight trust signal. Does not affect the GEO score.
"""

from __future__ import annotations

from geo_optimizer.models.results import SecurityHeadersResult

_CHECKED_HEADERS: dict[str, str] = {
    "strict-transport-security": "has_hsts",
    "content-security-policy": "has_csp",
    "x-content-type-options": "has_x_content_type_options",
    "referrer-policy": "has_referrer_policy",
    "permissions-policy": "has_permissions_policy",
    "x-frame-options": "has_x_frame_options",
}

_LABELS: dict[str, str] = {
    "has_hsts": "Strict-Transport-Security (HSTS)",
    "has_csp": "Content-Security-Policy",
    "has_x_content_type_options": "X-Content-Type-Options",
    "has_referrer_policy": "Referrer-Policy",
    "has_permissions_policy": "Permissions-Policy",
    "has_x_frame_options": "X-Frame-Options",
}


def audit_security_headers(response_headers: dict | None) -> SecurityHeadersResult:
    """Check the homepage response for standard security headers.

    Args:
        response_headers: HTTP response headers from the homepage fetch.

    Returns:
        SecurityHeadersResult with per-header presence and an overall grade.
    """
    result = SecurityHeadersResult(checked=True)
    headers_lower = {k.lower(): v for k, v in (response_headers or {}).items()}

    # CSP's frame-ancestors directive is an accepted modern substitute for
    # the legacy X-Frame-Options header.
    csp_value = headers_lower.get("content-security-policy", "")

    for header_key, attr in _CHECKED_HEADERS.items():
        present = header_key in headers_lower
        if attr == "has_x_frame_options" and not present:
            present = "frame-ancestors" in csp_value.lower()
        setattr(result, attr, present)
        if not present:
            result.missing.append(_LABELS[attr])

    result.headers_present_count = sum(1 for attr in _CHECKED_HEADERS.values() if getattr(result, attr))
    result.grade = _grade(result.headers_present_count, result.headers_total)
    return result


def _grade(present: int, total: int) -> str:
    ratio = present / total if total else 0
    if ratio >= 0.9:
        return "A"
    if ratio >= 0.7:
        return "B"
    if ratio >= 0.5:
        return "C"
    if ratio >= 0.25:
        return "D"
    return "F"
