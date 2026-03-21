"""
Simple Component Tests for PI Remover Microservices.

This script tests all components without requiring services to be running.
For full integration tests with services, use run_comprehensive_tests.ps1

Usage:
    python scripts/test_components.py
    python scripts/test_components.py --with-services  # Also test running services

Version: 2.9.0
"""

import os
import sys
import argparse

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_banner(text):
    """Print a banner."""
    print(f"\n{Colors.CYAN}{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}{Colors.RESET}\n")

def print_section(text):
    """Print a section header."""
    print(f"\n{Colors.YELLOW}--- {text} ---{Colors.RESET}\n")

def print_pass(test_name):
    """Print a passing test."""
    print(f"  {Colors.GREEN}[PASS]{Colors.RESET} {test_name}")
    return True

def print_fail(test_name, error=""):
    """Print a failing test."""
    msg = f"  {Colors.RED}[FAIL]{Colors.RESET} {test_name}"
    if error:
        msg += f" - {error}"
    print(msg)
    return False

def print_skip(test_name, reason=""):
    """Print a skipped test."""
    print(f"  {Colors.YELLOW}[SKIP]{Colors.RESET} {test_name} - {reason}")

def test_imports():
    """Test all module imports."""
    print_section("Module Import Tests")
    passed = 0
    failed = 0
    
    # Test 1: Core imports
    try:
        os.chdir(os.path.join(PROJECT_ROOT, 'api_service'))
        sys.path.insert(0, os.path.join(PROJECT_ROOT, 'api_service'))
        from app import app
        if print_pass("API Service (api_service/app.py)"):
            passed += 1
    except Exception as e:
        if print_fail("API Service", str(e)):
            failed += 1
    finally:
        os.chdir(PROJECT_ROOT)
    
    # Test 2: Web service
    try:
        os.chdir(os.path.join(PROJECT_ROOT, 'web_service'))
        sys.path.insert(0, os.path.join(PROJECT_ROOT, 'web_service'))
        # Clear cached imports
        if 'app' in sys.modules:
            del sys.modules['app']
        from app import app
        if print_pass("Web Service (web_service/app.py)"):
            passed += 1
    except Exception as e:
        if print_fail("Web Service", str(e)):
            failed += 1
    finally:
        os.chdir(PROJECT_ROOT)
    
    # Test 3: Shared config loader
    try:
        from shared.config_loader import ConfigLoader
        if print_pass("Config Loader (shared/config_loader.py)"):
            passed += 1
    except Exception as e:
        if print_fail("Config Loader", str(e)):
            failed += 1
    
    # Test 4: Shared logging
    try:
        from shared.logging_config import setup_structured_logging, get_correlation_id
        if print_pass("Logging Config (shared/logging_config.py)"):
            passed += 1
    except Exception as e:
        if print_fail("Logging Config", str(e)):
            failed += 1
    
    # Test 5: Redis client
    try:
        from shared.redis_client import RedisClient, InMemoryFallback
        if print_pass("Redis Client (shared/redis_client.py)"):
            passed += 1
    except Exception as e:
        if print_fail("Redis Client", str(e)):
            failed += 1
    
    # Test 6: API client
    try:
        from web_service.api_client import PIRemoverAPIClient, CircuitBreaker
        if print_pass("API Client (web_service/api_client.py)"):
            passed += 1
    except Exception as e:
        if print_fail("API Client", str(e)):
            failed += 1
    
    # Test 7: Security module
    try:
        from security import verify_bearer_token, generate_auth_token, SecurityConfig
        # Test SecurityConfig.load_clients classmethod
        SecurityConfig.load_clients()
        if print_pass("Security (security.py)"):
            passed += 1
    except Exception as e:
        print_fail("Security", str(e))
        failed += 1
    
    return passed, failed

def test_config_files():
    """Test all configuration files."""
    print_section("Configuration File Tests")
    passed = 0
    failed = 0
    
    import yaml
    
    config_files = [
        "config/api_service.yaml",
        "config/web_service.yaml",
        "config/clients.yaml",
        "config/redis.yaml",
        "config/logging.yaml"
    ]
    
    for config_file in config_files:
        filepath = os.path.join(PROJECT_ROOT, config_file)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
                if print_pass(config_file):
                    passed += 1
            except Exception as e:
                if print_fail(config_file, str(e)):
                    failed += 1
        else:
            print_fail(config_file, "File not found")
            failed += 1
    
    return passed, failed

def test_config_loading():
    """Test config loader functionality."""
    print_section("Config Loader Functionality")
    passed = 0
    failed = 0
    
    from shared.config_loader import ConfigLoader
    
    # Test loading a config file
    try:
        config = ConfigLoader.from_yaml(os.path.join(PROJECT_ROOT, "config/api_service.yaml"))
        assert config.get("service.name") is not None
        if print_pass("Load YAML config"):
            passed += 1
    except Exception as e:
        print_fail("Load YAML config", str(e))
        failed += 1
    
    # Test dot notation access
    try:
        config = ConfigLoader.from_yaml(os.path.join(PROJECT_ROOT, "config/api_service.yaml"))
        port = config.get("service.port", 8080)
        assert isinstance(port, int)
        if print_pass("Dot notation access"):
            passed += 1
    except Exception as e:
        print_fail("Dot notation access", str(e))
        failed += 1
    
    return passed, failed

def test_circuit_breaker():
    """Test circuit breaker functionality."""
    print_section("Circuit Breaker Tests")
    passed = 0
    failed = 0
    
    from web_service.api_client import CircuitBreaker, CircuitBreakerConfig, CircuitState
    
    # Test initial state
    try:
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30)
        cb = CircuitBreaker(config=config)
        assert cb.state == CircuitState.CLOSED
        if print_pass("Initial state is CLOSED"):
            passed += 1
    except Exception as e:
        print_fail("Initial state is CLOSED", str(e))
        failed += 1
    
    # Test recording failures
    try:
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30)
        cb = CircuitBreaker(config=config)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        if print_pass("Opens after threshold failures"):
            passed += 1
    except Exception as e:
        print_fail("Opens after threshold failures", str(e))
        failed += 1
    
    # Test recording success
    try:
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30)
        cb = CircuitBreaker(config=config)
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        if print_pass("Success resets failures"):
            passed += 1
    except Exception as e:
        print_fail("Success resets failures", str(e))
        failed += 1
    
    return passed, failed

def test_in_memory_fallback():
    """Test in-memory rate limiting fallback."""
    print_section("In-Memory Fallback Tests")
    passed = 0
    failed = 0
    
    import asyncio
    from shared.redis_client import InMemoryFallback
    
    # Test basic rate limiting
    try:
        async def test_counter():
            fallback = InMemoryFallback()
            key = "test:rate:limit"
            
            # Should return 1 on first increment
            count = await fallback.incr(key)
            assert count == 1
            
            # Should increment to 2
            count = await fallback.incr(key)
            assert count == 2
            
            return True
        
        result = asyncio.run(test_counter())
        if result and print_pass("Rate limit counter works"):
            passed += 1
    except Exception as e:
        print_fail("Rate limit counter works", str(e))
        failed += 1
    
    # Test cache
    try:
        async def test_cache():
            fallback = InMemoryFallback()
            await fallback.set("test:key", "test:value", 60)
            value = await fallback.get("test:key")
            assert value == "test:value"
            return True
        
        result = asyncio.run(test_cache())
        if result and print_pass("Cache get/set works"):
            passed += 1
    except Exception as e:
        print_fail("Cache get/set works", str(e))
        failed += 1
    
    return passed, failed

def test_services_running(api_url="http://localhost:8080", web_url="http://localhost:8082"):
    """Test running services if available."""
    print_section("Running Service Tests")
    
    try:
        import httpx
    except ImportError:
        print_skip("All service tests", "httpx not installed")
        return 0, 0
    
    passed = 0
    failed = 0
    
    # Test API docs
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{api_url}/docs")
            if response.status_code == 200:
                if print_pass("API Service /docs accessible"):
                    passed += 1
            else:
                print_fail("API Service /docs accessible", f"Status {response.status_code}")
                failed += 1
    except Exception as e:
        print_skip("API Service tests", "Service not running")
        return passed, failed
    
    # Test token generation
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                f"{api_url}/dev/auth/token",
                json={
                    "client_id": "pi-dev-client",
                    "client_secret": "YOUR_DEV_CLIENT_SECRET_HERE"
                }
            )
            if response.status_code == 200:
                token = response.json().get("access_token")
                if token:
                    if print_pass("Token generation"):
                        passed += 1
                    
                    # Test redaction
                    redact_response = client.post(
                        f"{api_url}/dev/v1/redact",
                        json={"text": "Email: test@example.com"},
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if redact_response.status_code == 200:
                        result = redact_response.json()
                        if "[EMAIL]" in result.get("redacted_text", ""):
                            if print_pass("Text redaction"):
                                passed += 1
                        else:
                            print_fail("Text redaction", "No [EMAIL] placeholder")
                            failed += 1
                    else:
                        print_fail("Text redaction", f"Status {redact_response.status_code}")
                        failed += 1
                else:
                    print_fail("Token generation", "No token in response")
                    failed += 1
            else:
                print_fail("Token generation", f"Status {response.status_code}")
                failed += 1
    except Exception as e:
        print_fail("Token generation", str(e))
        failed += 1
    
    # Test web service
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{web_url}/")
            if response.status_code == 200:
                if print_pass("Web Service home page"):
                    passed += 1
            else:
                print_skip("Web Service tests", "Service not running")
    except Exception:
        print_skip("Web Service tests", "Service not running")
    
    return passed, failed

def main():
    parser = argparse.ArgumentParser(description="Test PI Remover components")
    parser.add_argument("--with-services", action="store_true", 
                       help="Also test running services")
    parser.add_argument("--api-url", default="http://localhost:8080",
                       help="API service URL")
    parser.add_argument("--web-url", default="http://localhost:8082",
                       help="Web service URL")
    args = parser.parse_args()
    
    print_banner("PI Remover Component Tests v2.9.0")
    
    total_passed = 0
    total_failed = 0
    
    # Run tests
    p, f = test_imports()
    total_passed += p
    total_failed += f
    
    p, f = test_config_files()
    total_passed += p
    total_failed += f
    
    p, f = test_config_loading()
    total_passed += p
    total_failed += f
    
    p, f = test_circuit_breaker()
    total_passed += p
    total_failed += f
    
    p, f = test_in_memory_fallback()
    total_passed += p
    total_failed += f
    
    if args.with_services:
        p, f = test_services_running(args.api_url, args.web_url)
        total_passed += p
        total_failed += f
    
    # Summary
    print_banner("Test Results Summary")
    total = total_passed + total_failed
    pass_rate = (total_passed / total * 100) if total > 0 else 0
    
    print(f"  Total Tests: {total}")
    print(f"  {Colors.GREEN}Passed: {total_passed}{Colors.RESET}")
    print(f"  {Colors.RED if total_failed else Colors.GREEN}Failed: {total_failed}{Colors.RESET}")
    print(f"  Pass Rate: {pass_rate:.1f}%")
    print()
    
    if total_failed == 0:
        print(f"{Colors.GREEN}All tests passed!{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}Some tests failed.{Colors.RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
