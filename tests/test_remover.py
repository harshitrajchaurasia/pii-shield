"""
Tests for PI Remover Core Library
=================================
Unit tests for pi_remover

Run with:
    pytest tests/test_remover.py -v
    pytest tests/test_remover.py -v --cov=pi_remover
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pi_remover import PIRemover, PIRemoverConfig
from pi_remover.core import (
    Redaction,
    RedactionResult,
    DataCleaner,
    PIPatterns,
    __version__
)


# Fixtures
@pytest.fixture
def remover():
    """Create a PIRemover instance in fast mode (no NER)."""
    config = PIRemoverConfig(enable_ner=False)
    return PIRemover(config)


@pytest.fixture
def remover_full():
    """Create a PIRemover instance in full mode (with NER if available)."""
    config = PIRemoverConfig(enable_ner=True)
    return PIRemover(config)


# Email Tests
class TestEmailRedaction:
    """Test email redaction."""

    def test_basic_email(self, remover):
        """Test basic email redaction."""
        text = "Contact john@example.com for help"
        result = remover.redact(text)
        assert "[EMAIL]" in result
        assert "john@example.com" not in result

    def test_multiple_emails(self, remover):
        """Test multiple emails in same text."""
        text = "Email john@test.com or jane@example.org"
        result = remover.redact(text)
        assert result.count("[EMAIL]") == 2

    def test_email_with_subdomain(self, remover):
        """Test email with subdomain."""
        text = "Contact support@mail.company.co.uk"
        result = remover.redact(text)
        assert "[EMAIL]" in result

    def test_email_with_plus(self, remover):
        """Test email with plus sign."""
        text = "Email john+newsletter@gmail.com"
        result = remover.redact(text)
        assert "[EMAIL]" in result

    def test_tcs_email(self, remover):
        """Test TCS domain email."""
        text = "Contact gws.support@tcs.com"
        result = remover.redact(text)
        assert "[EMAIL]" in result


# Phone Number Tests
class TestPhoneRedaction:
    """Test phone number redaction."""

    def test_indian_phone_10digit(self, remover):
        """Test Indian 10-digit mobile."""
        text = "Call me at 9876543210"
        result = remover.redact(text)
        assert "[PHONE]" in result

    def test_indian_phone_with_91(self, remover):
        """Test Indian phone with +91."""
        text = "Phone: +91 9876543210"
        result = remover.redact(text)
        assert "[PHONE]" in result

    def test_indian_phone_no_space(self, remover):
        """Test Indian phone without space after +91."""
        text = "Call +919876543210"
        result = remover.redact(text)
        assert "[PHONE]" in result

    def test_uk_phone(self, remover):
        """Test UK phone number."""
        text = "UK DID: +442030028019"
        result = remover.redact(text)
        assert "[PHONE]" in result

    def test_uk_phone_with_spaces(self, remover):
        """Test UK phone with spaces."""
        text = "Call +44 7405 186893"
        result = remover.redact(text)
        assert "[PHONE]" in result

    def test_us_phone(self, remover):
        """Test US phone number."""
        text = "Call +1 555-123-4567"
        result = remover.redact(text)
        assert "[PHONE]" in result

    def test_toll_free(self, remover):
        """Test toll-free number."""
        text = "Call 1800-267-6563"
        result = remover.redact(text)
        assert "[PHONE]" in result

    def test_landline(self, remover):
        """Test Indian landline."""
        text = "Office: 022-12345678"
        result = remover.redact(text)
        assert "[PHONE]" in result


# Employee ID Tests
class TestEmployeeIdRedaction:
    """Test employee ID redaction."""

    def test_prefixed_ad(self, remover):
        """Test AD prefixed employee ID."""
        text = "Account: ad.2349024"
        result = remover.redact(text)
        assert "[EMP_ID]" in result

    def test_prefixed_pr(self, remover):
        """Test PR prefixed employee ID."""
        text = "User pr.1234567"
        result = remover.redact(text)
        assert "[EMP_ID]" in result

    def test_prefixed_vo(self, remover):
        """Test VO prefixed employee ID."""
        text = "VoIP: vo.1234567"
        result = remover.redact(text)
        assert "[EMP_ID]" in result

    def test_prefixed_da(self, remover):
        """Test DA prefixed employee ID."""
        text = "Domain Admin: da.2185655"
        result = remover.redact(text)
        assert "[EMP_ID]" in result

    def test_employee_id_in_context(self, remover):
        """Test standalone employee ID with context."""
        text = "Contact user 1234567 for help"
        result = remover.redact(text)
        assert "[EMP_ID]" in result

    def test_employee_id_with_keyword(self, remover):
        """Test employee ID with keyword."""
        text = "Emp ID: 2345678"
        result = remover.redact(text)
        assert "[EMP_ID]" in result

    def test_ldap_cn_pattern(self, remover):
        """Test LDAP CN pattern."""
        text = "CN=1860950,OU=Users"
        result = remover.redact(text)
        assert "[EMP_ID]" in result


# Name Tests
class TestNameRedaction:
    """Test name redaction."""

    def test_name_with_title_mr(self, remover):
        """Test name with Mr. title."""
        text = "Contact Mr. Rahul Sharma"
        result = remover.redact(text)
        assert "[NAME]" in result

    def test_name_with_title_ms(self, remover):
        """Test name with Ms. title."""
        text = "Contact Ms. Priya Patel"
        result = remover.redact(text)
        assert "[NAME]" in result

    def test_indian_name_dictionary(self, remover):
        """Test Indian name from dictionary."""
        text = "Assigned to Amit Kumar"
        result = remover.redact(text)
        assert "[NAME]" in result

    def test_all_caps_name(self, remover):
        """Test ALL CAPS name."""
        text = "User: SUMAN KUMAR"
        result = remover.redact(text)
        assert "[NAME]" in result


# IP Address Tests
class TestIPRedaction:
    """Test IP address redaction."""

    def test_ipv4_basic(self, remover):
        """Test basic IPv4."""
        text = "Server IP: 192.168.1.1"
        result = remover.redact(text)
        # IP detection may vary based on implementation
        assert "[IP]" in result or "192.168.1.1" not in result

    def test_ipv4_with_port(self, remover):
        """Test IPv4 with port."""
        text = "Connect to 10.0.0.1:8080"
        result = remover.redact(text)
        # IP detection may vary based on implementation
        assert "[IP]" in result or "10.0.0.1" not in result

    def test_mac_address(self, remover):
        """Test MAC address."""
        text = "MAC: 00:1A:2B:3C:4D:5E"
        result = remover.redact(text)
        # MAC detection may be handled differently
        assert "[MAC]" in result or "[IP]" in result or "00:1A:2B:3C:4D:5E" not in result


# Other PI Tests
class TestOtherPIRedaction:
    """Test other PI type redaction."""

    def test_asset_id(self, remover):
        """Test asset ID."""
        text = "Asset: 01HW1742875"
        result = remover.redact(text)
        assert "[ASSET_ID]" in result

    def test_hostname(self, remover):
        """Test hostname."""
        text = "Server: ER06SVR40615265"
        result = remover.redact(text)
        assert "[HOSTNAME]" in result

    def test_url(self, remover):
        """Test URL redaction."""
        text = "Visit https://sharepoint.company.com/site"
        result = remover.redact(text)
        assert "[URL]" in result

    def test_upi_id(self, remover):
        """Test UPI ID."""
        text = "Pay to user@paytm"
        result = remover.redact(text)
        assert "[UPI]" in result

    def test_aadhaar(self, remover):
        """Test Aadhaar number."""
        text = "Aadhaar: 1234 5678 9012"
        result = remover.redact(text)
        assert "[AADHAAR]" in result

    def test_pan(self, remover):
        """Test PAN card."""
        text = "PAN: ABCDE1234F"
        result = remover.redact(text)
        assert "[PAN]" in result

    def test_credential(self, remover):
        """Test credential/password."""
        text = "Password is: TempPass@123"
        result = remover.redact(text)
        assert "[CREDENTIAL]" in result


# Signature Block Tests
class TestSignatureRedaction:
    """Test signature block redaction."""

    def test_thanks_and_regards(self, remover):
        """Test Thanks & Regards signature."""
        text = """Please help with this issue.

Thanks & Regards,
Vaishnavi Saswade
Employee ID: 1321823"""
        result = remover.redact(text)
        assert "[SIGNATURE]" in result

    def test_best_regards(self, remover):
        """Test Best Regards signature."""
        text = """Let me know if you need anything.

Best Regards,
John Doe"""
        result = remover.redact(text)
        assert "[SIGNATURE]" in result


# Redact With Details Tests
class TestRedactWithDetails:
    """Test redact_with_details method."""

    def test_returns_redaction_result(self, remover):
        """Test that method returns RedactionResult."""
        text = "Email: test@example.com"
        result = remover.redact_with_details(text)
        assert isinstance(result, RedactionResult)

    def test_redactions_list(self, remover):
        """Test redactions list is populated."""
        text = "Email: test@example.com, Phone: +91 9876543210"
        result = remover.redact_with_details(text)
        assert len(result.redactions) >= 2

    def test_redaction_has_confidence(self, remover):
        """Test each redaction has confidence score."""
        text = "Email: test@example.com"
        result = remover.redact_with_details(text)
        for redaction in result.redactions:
            assert 0.0 <= redaction.confidence <= 1.0

    def test_redaction_has_method(self, remover):
        """Test each redaction has detection method."""
        text = "Email: test@example.com"
        result = remover.redact_with_details(text)
        for redaction in result.redactions:
            assert redaction.detection_method in ["regex", "ner", "dictionary", "pattern", "context", "regex_context"]

    def test_processing_time(self, remover):
        """Test processing time is recorded."""
        text = "Email: test@example.com"
        result = remover.redact_with_details(text)
        assert result.processing_time_ms > 0

    def test_to_dict(self, remover):
        """Test to_dict method."""
        text = "Email: test@example.com"
        result = remover.redact_with_details(text)
        d = result.to_dict()
        assert "redacted_text" in d
        assert "redactions" in d
        assert "processing_time_ms" in d


# Batch Processing Tests
class TestBatchProcessing:
    """Test batch processing methods."""

    def test_redact_batch(self, remover):
        """Test batch redaction."""
        texts = [
            "Email: test@example.com",
            "Phone: +91 9876543210",
            "Name: Rahul Sharma"
        ]
        results = remover.redact_batch(texts)
        assert len(results) == 3
        assert "[EMAIL]" in results[0]
        assert "[PHONE]" in results[1]

    def test_redact_batch_with_details(self, remover):
        """Test batch redaction with details."""
        texts = [
            "Email: test@example.com",
            "Phone: +91 9876543210"
        ]
        results = remover.redact_batch_with_details(texts)
        assert len(results) == 2
        assert all(isinstance(r, RedactionResult) for r in results)


# Health Check Tests
class TestHealthCheck:
    """Test health check method."""

    def test_health_check_returns_dict(self, remover):
        """Test health check returns dictionary."""
        health = remover.health_check()
        assert isinstance(health, dict)

    def test_health_check_has_status(self, remover):
        """Test health check has status field."""
        health = remover.health_check()
        assert "status" in health
        assert health["status"] == "healthy"

    def test_health_check_has_version(self, remover):
        """Test health check has version."""
        health = remover.health_check()
        assert "version" in health
        assert health["version"] == __version__

    def test_health_check_has_mode(self, remover):
        """Test health check has mode."""
        health = remover.health_check()
        assert "mode" in health
        # This fixture uses enable_ner=False, so mode should be "fast"
        assert health["mode"] == "fast"


# Data Cleaner Tests
class TestDataCleaner:
    """Test DataCleaner class."""

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        text = "Hello   World"
        result = DataCleaner.clean(text)
        assert "   " not in result

    def test_decode_html_entities(self):
        """Test HTML entity decoding."""
        text = "Test &amp; Example"
        result = DataCleaner.clean(text)
        assert "&amp;" not in result

    def test_handles_empty_string(self):
        """Test handling of empty string."""
        result = DataCleaner.clean("")
        assert result == ""

    def test_handles_none(self):
        """Test handling of None."""
        result = DataCleaner.clean(None)
        # DataCleaner may return None or empty string for None input
        assert result == "" or result is None


# Configuration Tests
class TestConfiguration:
    """Test configuration options."""

    def test_disable_email_redaction(self):
        """Test disabling email redaction."""
        config = PIRemoverConfig(enable_ner=False, redact_emails=False)
        remover = PIRemover(config)
        text = "Email: test@example.com"
        result = remover.redact(text)
        assert "[EMAIL]" not in result

    def test_disable_phone_redaction(self):
        """Test disabling phone redaction."""
        config = PIRemoverConfig(enable_ner=False, redact_phones=False)
        remover = PIRemover(config)
        text = "Phone: +91 9876543210"
        result = remover.redact(text)
        assert "[PHONE]" not in result

    def test_use_generic_token(self):
        """Test using generic REDACTED token."""
        config = PIRemoverConfig(enable_ner=False, use_typed_tokens=False)
        remover = PIRemover(config)
        text = "Email: test@example.com"
        result = remover.redact(text)
        assert "[REDACTED]" in result


# Edge Cases
class TestEdgeCases:
    """Test edge cases."""

    def test_empty_string(self, remover):
        """Test empty string."""
        result = remover.redact("")
        assert result == ""

    def test_whitespace_only(self, remover):
        """Test whitespace-only string."""
        result = remover.redact("   ")
        assert result.strip() == ""

    def test_no_pi(self, remover):
        """Test string with no PI."""
        text = "This is a normal sentence with no personal information."
        result = remover.redact(text)
        assert "[" not in result or result == text

    def test_unicode_text(self, remover):
        """Test Unicode text."""
        text = "Contact user@example.com with query: \u00e9\u00e8\u00ea"
        result = remover.redact(text)
        assert "[EMAIL]" in result

    def test_very_long_text(self, remover):
        """Test very long text."""
        text = "Email: test@example.com " * 1000
        result = remover.redact(text)
        assert result.count("[EMAIL]") == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
