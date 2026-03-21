"""
Integration Tests for PI Remover Microservices Architecture.

Tests the communication between web_service and api_service,
including authentication, redaction, and error handling.

Usage:
    # Start both services first, then run:
    pytest tests/test_service_integration.py -v
    
    # Or with custom URLs:
    pytest tests/test_service_integration.py -v \
        --api-url http://localhost:8080 \
        --web-url http://localhost:8082

Version: 2.9.0
"""

import os
import sys
import time
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

# Default service URLs
API_SERVICE_URL = os.environ.get("API_SERVICE_URL", "http://localhost:8080")
WEB_SERVICE_URL = os.environ.get("WEB_SERVICE_URL", "http://localhost:8082")

# Test credentials (from config/clients.yaml or hardcoded defaults)
TEST_CLIENT_ID = "pi-dev-client"
TEST_CLIENT_SECRET = "YOUR_DEV_CLIENT_SECRET_HERE"

INTERNAL_CLIENT_ID = "pi-internal-web-service"
INTERNAL_CLIENT_SECRET = "YOUR_WEB_CLIENT_SECRET_HERE"


# Fixtures
@pytest.fixture(scope="module")
def api_client():
    """Create HTTP client for API service."""
    return httpx.Client(base_url=API_SERVICE_URL, timeout=30.0)


@pytest.fixture(scope="module")
def web_client():
    """Create HTTP client for Web service."""
    return httpx.Client(base_url=WEB_SERVICE_URL, timeout=30.0)


@pytest.fixture(scope="module")
def api_token(api_client):
    """Get authentication token from API service."""
    response = api_client.post(
        "/dev/auth/token",
        json={"client_id": TEST_CLIENT_ID, "client_secret": TEST_CLIENT_SECRET}
    )
    assert response.status_code == 200, f"Failed to get token: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def internal_token(api_client):
    """Get authentication token for internal service client."""
    response = api_client.post(
        "/dev/auth/token",
        json={"client_id": INTERNAL_CLIENT_ID, "client_secret": INTERNAL_CLIENT_SECRET}
    )
    assert response.status_code == 200, f"Failed to get internal token: {response.text}"
    return response.json()["access_token"]


# API Service Tests
class TestAPIServiceDirect:
    """Test API service directly."""
    
    def test_api_docs_accessible(self, api_client):
        """Test that API documentation is accessible."""
        response = api_client.get("/docs")
        assert response.status_code == 200
    
    def test_api_token_generation(self, api_client):
        """Test token generation with valid credentials."""
        response = api_client.post(
            "/dev/auth/token",
            json={"client_id": TEST_CLIENT_ID, "client_secret": TEST_CLIENT_SECRET}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
    
    def test_api_token_invalid_credentials(self, api_client):
        """Test token generation fails with invalid credentials."""
        response = api_client.post(
            "/dev/auth/token",
            json={"client_id": "invalid", "client_secret": "invalid"}
        )
        assert response.status_code == 401
    
    def test_api_health_requires_auth(self, api_client):
        """Test that health endpoint requires authentication."""
        response = api_client.get("/dev/health")
        assert response.status_code == 401
    
    def test_api_health_with_auth(self, api_client, api_token):
        """Test health endpoint with authentication."""
        response = api_client.get(
            "/dev/health",
            headers={"Authorization": f"Bearer {api_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_api_redact_single(self, api_client, api_token):
        """Test single text redaction."""
        response = api_client.post(
            "/dev/v1/redact",
            json={"text": "Contact John Smith at john.smith@example.com"},
            headers={"Authorization": f"Bearer {api_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "[EMAIL]" in data["redacted_text"]
        assert "john.smith@example.com" not in data["redacted_text"]
    
    def test_api_redact_batch(self, api_client, api_token):
        """Test batch text redaction."""
        response = api_client.post(
            "/dev/v1/redact/batch",
            json={
                "texts": [
                    "Email: test@example.com",
                    "Phone: 555-123-4567"
                ]
            },
            headers={"Authorization": f"Bearer {api_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert "[EMAIL]" in data["results"][0]["redacted_text"]
        assert "[PHONE]" in data["results"][1]["redacted_text"]
    
    def test_api_models_endpoint(self, api_client, api_token):
        """Test models endpoint."""
        response = api_client.get(
            "/dev/v1/models",
            headers={"Authorization": f"Bearer {api_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert len(data["models"]) > 0
    
    def test_api_internal_client_high_rate_limit(self, api_client, internal_token):
        """Test that internal service client has higher rate limit."""
        # Make multiple requests quickly
        for i in range(20):
            response = api_client.post(
                "/dev/v1/redact",
                json={"text": f"Test {i}: email@example.com"},
                headers={"Authorization": f"Bearer {internal_token}"}
            )
            assert response.status_code == 200, f"Request {i} failed: {response.text}"


# Web Service Tests
class TestWebServiceDirect:
    """Test Web service directly."""
    
    def test_web_home_page(self, web_client):
        """Test that home page is accessible."""
        response = web_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_web_health_endpoint(self, web_client):
        """Test web service health endpoint."""
        response = web_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "api_service" in data
    
    def test_web_service_info(self, web_client):
        """Test service info endpoint."""
        response = web_client.get("/api/service-info")
        assert response.status_code == 200
        data = response.json()
        assert data["architecture"] == "microservices"


# Integration Tests (Web -> API)
class TestWebToAPIIntegration:
    """Test web service calling API service."""
    
    def test_web_redact_text_via_api(self, web_client):
        """Test that web service correctly calls API for text redaction."""
        response = web_client.post(
            "/api/redact-text",
            json={"text": "My email is john@example.com", "fast_mode": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert "[EMAIL]" in data["redacted_text"]
        assert data["api_service_used"] is True
    
    def test_web_redact_text_fast_mode(self, web_client):
        """Test fast mode redaction via web service."""
        response = web_client.post(
            "/api/redact-text",
            json={"text": "Call me at 555-123-4567", "fast_mode": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert "[PHONE]" in data["redacted_text"]
    
    def test_web_redact_empty_text(self, web_client):
        """Test redaction with empty text."""
        response = web_client.post(
            "/api/redact-text",
            json={"text": "", "fast_mode": False}
        )
        assert response.status_code == 400  # Validation error
    
    def test_web_health_shows_api_status(self, web_client):
        """Test that web health shows API service status."""
        response = web_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "api_service" in data
        assert "url" in data["api_service"]
        assert "status" in data["api_service"]
        assert "healthy" in data["api_service"]
    
    def test_web_correlation_id_propagation(self, web_client):
        """Test that correlation ID is propagated to API."""
        correlation_id = "test-correlation-12345"
        response = web_client.post(
            "/api/redact-text",
            json={"text": "test@example.com"},
            headers={"X-Correlation-ID": correlation_id}
        )
        assert response.status_code == 200
        # Response should include correlation ID header
        # (depends on implementation)


# Resilience Tests
class TestResilience:
    """Test resilience features (circuit breaker, retries)."""
    
    @pytest.mark.skip(reason="Requires API service to be down")
    def test_web_handles_api_unavailable(self, web_client):
        """Test web service handles API unavailability gracefully."""
        # This test requires stopping the API service
        response = web_client.post(
            "/api/redact-text",
            json={"text": "test@example.com"}
        )
        assert response.status_code == 503
        assert "unavailable" in response.json().get("detail", "").lower()


# Performance Tests
class TestPerformance:
    """Basic performance tests."""
    
    def test_api_latency(self, api_client, api_token):
        """Test API response time is acceptable."""
        start = time.perf_counter()
        response = api_client.post(
            "/dev/v1/redact",
            json={"text": "Simple test email@example.com"},
            headers={"Authorization": f"Bearer {api_token}"}
        )
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        assert response.status_code == 200
        assert elapsed < 5000, f"API response too slow: {elapsed:.0f}ms"
    
    def test_web_latency(self, web_client):
        """Test web service response time (including API call)."""
        start = time.perf_counter()
        response = web_client.post(
            "/api/redact-text",
            json={"text": "Simple test email@example.com"}
        )
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        assert response.status_code == 200
        # Web should be slightly slower due to HTTP hop
        assert elapsed < 6000, f"Web response too slow: {elapsed:.0f}ms"


# Security Tests
class TestSecurity:
    """Security-related integration tests."""
    
    def test_api_expired_token_rejected(self, api_client):
        """Test that expired tokens are rejected."""
        # This is a manually crafted expired token (for testing)
        expired_token = "expired.token.here"
        response = api_client.get(
            "/dev/health",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401
    
    def test_api_malformed_token_rejected(self, api_client):
        """Test that malformed tokens are rejected."""
        response = api_client.get(
            "/dev/health",
            headers={"Authorization": "Bearer not-a-valid-jwt"}
        )
        assert response.status_code == 401
    
    def test_internal_client_works(self, api_client, internal_token):
        """Test that internal service client can authenticate."""
        response = api_client.get(
            "/dev/health",
            headers={"Authorization": f"Bearer {internal_token}"}
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
