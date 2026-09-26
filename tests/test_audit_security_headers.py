"""Tests for the Security Headers check (informational, does not affect GEO score)."""

from __future__ import annotations

from geo_optimizer.core.audit_security_headers import audit_security_headers


class TestAuditSecurityHeaders:
    def test_audit_security_headers_all_present_returns_grade_a(self):
        headers = {
            "Strict-Transport-Security": "max-age=63072000",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "geolocation=()",
            "X-Frame-Options": "DENY",
        }

        result = audit_security_headers(headers)

        assert result.checked is True
        assert result.headers_present_count == 6
        assert result.grade == "A"
        assert result.missing == []

    def test_audit_security_headers_none_present_returns_grade_f(self):
        result = audit_security_headers({})

        assert result.headers_present_count == 0
        assert result.grade == "F"
        assert len(result.missing) == 6

    def test_audit_security_headers_handles_none_input(self):
        result = audit_security_headers(None)
        assert result.headers_present_count == 0
        assert result.grade == "F"

    def test_audit_security_headers_header_keys_are_case_insensitive(self):
        headers = {"strict-transport-security": "max-age=1", "CONTENT-SECURITY-POLICY": "default-src 'self'"}

        result = audit_security_headers(headers)

        assert result.has_hsts is True
        assert result.has_csp is True

    def test_audit_security_headers_csp_frame_ancestors_satisfies_xframe(self):
        headers = {"Content-Security-Policy": "frame-ancestors 'self'"}

        result = audit_security_headers(headers)

        assert result.has_x_frame_options is True
        assert "X-Frame-Options" not in result.missing

    def test_audit_security_headers_missing_lists_correct_labels(self):
        headers = {"Strict-Transport-Security": "max-age=1"}

        result = audit_security_headers(headers)

        assert "Strict-Transport-Security (HSTS)" not in result.missing
        assert "Content-Security-Policy" in result.missing
        assert "X-Frame-Options" in result.missing

    def test_audit_security_headers_partial_present_grades_between_a_and_f(self):
        headers = {
            "Strict-Transport-Security": "max-age=1",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
        }

        result = audit_security_headers(headers)

        assert result.headers_present_count == 3
        assert result.grade == "C"
