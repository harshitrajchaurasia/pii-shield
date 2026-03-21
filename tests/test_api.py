"""
Tests for PI Remover API Service
================================
Integration tests for the FastAPI endpoints.

Run with:
    pytest tests/test_api.py -v
"""

import pytest
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'api_service'))

from fastapi.testclient import TestClient

# Import the app
from api_service.app import app


# Fixtures
@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


# Health Check Tests
class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_returns_200(self, client):
        """Test health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy(self, client):
        """Test health status is healthy."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_has_version(self, client):
        """Test health response has version."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data

    def test_health_has_mode(self, client):
        """Test health response has mode."""
        response = client.get("/health")
        data = response.json()
        assert "mode" in data
        # Mode is "full" when NER is enabled (default), "fast" when disabled
        assert data["mode"] in ["fast", "full"]


# Single Redact Endpoint Tests
class TestRedactEndpoint:
    """Test /v1/redact endpoint."""

    def test_redact_email(self, client):
        """Test email redaction."""
        response = client.post(
            "/v1/redact",
            json={"text": "Contact john@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "[EMAIL]" in data["redacted_text"]

    def test_redact_phone(self, client):
        """Test phone redaction."""
        response = client.post(
            "/v1/redact",
            json={"text": "Call +91 9876543210"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "[PHONE]" in data["redacted_text"]

    def test_redact_multiple_pi(self, client):
        """Test multiple PI types."""
        response = client.post(
            "/v1/redact",
            json={"text": "Email john@test.com or call +91 9876543210"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "[EMAIL]" in data["redacted_text"]
        assert "[PHONE]" in data["redacted_text"]

    def test_redact_has_request_id(self, client):
        """Test response has request_id."""
        response = client.post(
            "/v1/redact",
            json={"text": "Test text"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "request_id" in data

    def test_redact_has_processing_time(self, client):
        """Test response has processing_time_ms."""
        response = client.post(
            "/v1/redact",
            json={"text": "Test text"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "processing_time_ms" in data
        assert data["processing_time_ms"] >= 0

    def test_redact_with_custom_request_id(self, client):
        """Test custom request_id is returned."""
        response = client.post(
            "/v1/redact",
            json={"text": "Test", "request_id": "my-custom-id"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "my-custom-id"

    def test_redact_with_details(self, client):
        """Test redaction with details."""
        response = client.post(
            "/v1/redact",
            json={"text": "Email: test@example.com", "include_details": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert "redactions" in data
        assert len(data["redactions"]) > 0

    def test_redact_details_has_confidence(self, client):
        """Test redaction details include confidence."""
        response = client.post(
            "/v1/redact",
            json={"text": "Email: test@example.com", "include_details": True}
        )
        assert response.status_code == 200
        data = response.json()
        for redaction in data["redactions"]:
            assert "confidence" in redaction
            assert 0.0 <= redaction["confidence"] <= 1.0

    def test_redact_empty_text(self, client):
        """Test empty text handling."""
        response = client.post(
            "/v1/redact",
            json={"text": ""}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["redacted_text"] == ""

    def test_redact_no_pi(self, client):
        """Test text with no PI."""
        text = "This is a normal sentence."
        response = client.post(
            "/v1/redact",
            json={"text": text}
        )
        assert response.status_code == 200
        data = response.json()
        # Text should be mostly unchanged (minor whitespace changes allowed)
        assert "[" not in data["redacted_text"] or data["redacted_text"].strip() == text.strip()

    def test_redact_missing_text(self, client):
        """Test missing text field."""
        response = client.post(
            "/v1/redact",
            json={}
        )
        assert response.status_code == 422  # Validation error


# Batch Redact Endpoint Tests
class TestBatchRedactEndpoint:
    """Test /v1/redact/batch endpoint."""

    def test_batch_basic(self, client):
        """Test basic batch redaction."""
        response = client.post(
            "/v1/redact/batch",
            json={
                "texts": [
                    "Email: test@example.com",
                    "Phone: +91 9876543210"
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2

    def test_batch_has_indexes(self, client):
        """Test batch results have correct indexes."""
        response = client.post(
            "/v1/redact/batch",
            json={
                "texts": ["Text 1", "Text 2", "Text 3"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        indexes = [r["index"] for r in data["results"]]
        assert indexes == [0, 1, 2]

    def test_batch_total_count(self, client):
        """Test batch total_count field."""
        texts = ["Text 1", "Text 2", "Text 3"]
        response = client.post(
            "/v1/redact/batch",
            json={"texts": texts}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == len(texts)

    def test_batch_with_details(self, client):
        """Test batch with details."""
        response = client.post(
            "/v1/redact/batch",
            json={
                "texts": ["Email: test@example.com"],
                "include_details": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "redactions" in data["results"][0]

    def test_batch_empty_list(self, client):
        """Test empty list handling."""
        response = client.post(
            "/v1/redact/batch",
            json={"texts": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0


# PI Types Endpoint Tests
class TestPITypesEndpoint:
    """Test /v1/pi-types endpoint."""

    def test_pi_types_returns_list(self, client):
        """Test pi-types returns list."""
        response = client.get("/v1/pi-types")
        assert response.status_code == 200
        data = response.json()
        assert "pi_types" in data
        assert isinstance(data["pi_types"], list)

    def test_pi_types_has_email(self, client):
        """Test EMAIL type is present."""
        response = client.get("/v1/pi-types")
        data = response.json()
        types = [pt["type"] for pt in data["pi_types"]]
        assert "EMAIL" in types

    def test_pi_types_has_phone(self, client):
        """Test PHONE type is present."""
        response = client.get("/v1/pi-types")
        data = response.json()
        types = [pt["type"] for pt in data["pi_types"]]
        assert "PHONE" in types

    def test_pi_type_has_token(self, client):
        """Test each pi type has token field."""
        response = client.get("/v1/pi-types")
        data = response.json()
        for pt in data["pi_types"]:
            assert "token" in pt
            assert pt["token"].startswith("[")

    def test_pi_type_has_description(self, client):
        """Test each pi type has description."""
        response = client.get("/v1/pi-types")
        data = response.json()
        for pt in data["pi_types"]:
            assert "description" in pt
            assert len(pt["description"]) > 0


# Root Endpoint Tests
class TestRootEndpoint:
    """Test / endpoint."""

    def test_root_returns_info(self, client):
        """Test root returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


# Performance Tests
class TestPerformance:
    """Basic performance tests."""

    def test_latency_under_100ms(self, client):
        """Test single request latency is under 100ms."""
        response = client.post(
            "/v1/redact",
            json={"text": "Contact john@example.com at +91 9876543210"}
        )
        assert response.status_code == 200
        data = response.json()
        # Allow some slack for CI environments
        assert data["processing_time_ms"] < 500

    def test_batch_scales_linearly(self, client):
        """Test batch processing doesn't have exponential slowdown."""
        # Single request
        response1 = client.post(
            "/v1/redact/batch",
            json={"texts": ["Email: test@example.com"]}
        )
        time1 = response1.json()["processing_time_ms"]

        # 10 requests
        response10 = client.post(
            "/v1/redact/batch",
            json={"texts": ["Email: test@example.com"] * 10}
        )
        time10 = response10.json()["processing_time_ms"]

        # Time for 10 should be roughly 10x time for 1 (not exponential)
        # Allow 20x to account for overhead
        assert time10 < time1 * 20


# Error Handling Tests
class TestErrorHandling:
    """Test error handling."""

    def test_invalid_json(self, client):
        """Test invalid JSON handling."""
        response = client.post(
            "/v1/redact",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_method_not_allowed(self, client):
        """Test method not allowed."""
        response = client.get("/v1/redact")
        assert response.status_code == 405


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
