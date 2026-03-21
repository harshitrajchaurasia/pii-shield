#!/bin/bash
# =============================================================================
# Comprehensive Test Script for PI Remover Microservices Architecture
# =============================================================================
#
# DESCRIPTION:
#   This script starts all services in separate terminals and runs comprehensive tests:
#   - API Service (Port 8080)
#   - Web Service (Port 8082)
#   - Redis (Port 6379, optional)
#   - Integration Tests
#   - Component Tests
#
# USAGE:
#   ./scripts/run_comprehensive_tests.sh
#   ./scripts/run_comprehensive_tests.sh --skip-redis --skip-cleanup
#   ./scripts/run_comprehensive_tests.sh --test-only
#
# OPTIONS:
#   --config-path PATH    Path to configuration files (default: "config")
#   --skip-redis          Skip Redis startup (uses in-memory fallback)
#   --skip-cleanup        Keep services running after tests complete
#   --test-only           Only run tests, assume services are already running
#
# VERSION: 2.9.0
# =============================================================================

set -e

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

CONFIG_PATH="config"
SKIP_REDIS=false
SKIP_CLEANUP=false
TEST_ONLY=false
STARTUP_WAIT_SECONDS=60

API_SERVICE_PORT=8080
WEB_SERVICE_PORT=8082
REDIS_PORT=6379

API_SERVICE_URL="http://localhost:${API_SERVICE_PORT}"
WEB_SERVICE_URL="http://localhost:${WEB_SERVICE_PORT}"

# Test credentials
TEST_CLIENT_ID="pi-dev-client"
TEST_CLIENT_SECRET="YOUR_DEV_CLIENT_SECRET_HERE"

# Track started processes
declare -a STARTED_PIDS=()
declare -a STARTED_CONTAINERS=()

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Auth token
AUTH_TOKEN=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# =============================================================================
# PARSE ARGUMENTS
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --config-path)
            CONFIG_PATH="$2"
            shift 2
            ;;
        --skip-redis)
            SKIP_REDIS=true
            shift
            ;;
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --test-only)
            TEST_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

write_banner() {
    local title="$1"
    echo ""
    echo -e "${CYAN}======================================================================${NC}"
    echo -e "${CYAN}  $title${NC}"
    echo -e "${CYAN}======================================================================${NC}"
    echo ""
}

write_section() {
    local title="$1"
    echo ""
    echo -e "${YELLOW}--- $title ---${NC}"
    echo ""
}

write_test_result() {
    local test_name="$1"
    local passed="$2"
    local message="${3:-}"
    
    if [[ "$passed" == "true" ]]; then
        echo -e "  ${GREEN}[PASS]${NC} $test_name"
        ((TESTS_PASSED++))
    else
        echo -e "  ${RED}[FAIL]${NC} $test_name - $message"
        ((TESTS_FAILED++))
    fi
}

write_test_skipped() {
    local test_name="$1"
    local reason="$2"
    echo -e "  ${YELLOW}[SKIP]${NC} $test_name - $reason"
    ((TESTS_SKIPPED++))
}

check_port() {
    local port=$1
    if command -v lsof &> /dev/null; then
        lsof -i :$port &> /dev/null
    elif command -v netstat &> /dev/null; then
        netstat -tuln | grep -q ":$port "
    elif command -v ss &> /dev/null; then
        ss -tuln | grep -q ":$port "
    else
        return 1
    fi
}

wait_for_service() {
    local url="$1"
    local service_name="$2"
    local timeout="${3:-60}"
    local headers="${4:-}"
    
    echo -n "  Waiting for $service_name at $url..."
    
    local start_time=$(date +%s)
    local end_time=$((start_time + timeout))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        if curl -s -o /dev/null -w "%{http_code}" "$url" $headers | grep -q "200\|301\|302"; then
            echo -e " ${GREEN}Ready!${NC}"
            return 0
        fi
        sleep 2
        echo -n "."
    done
    
    echo -e " ${RED}Timeout!${NC}"
    return 1
}

get_auth_token() {
    local response
    response=$(curl -s -X POST "${API_SERVICE_URL}/dev/auth/token" \
        -H "Content-Type: application/json" \
        -d "{\"client_id\": \"${TEST_CLIENT_ID}\", \"client_secret\": \"${TEST_CLIENT_SECRET}\"}" 2>/dev/null)
    
    if [[ $? -eq 0 ]]; then
        AUTH_TOKEN=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)
        if [[ -n "$AUTH_TOKEN" ]]; then
            return 0
        fi
    fi
    return 1
}

# =============================================================================
# SERVICE STARTUP FUNCTIONS
# =============================================================================

start_redis_service() {
    if [[ "$SKIP_REDIS" == "true" ]]; then
        echo -e "  ${YELLOW}Skipping Redis (using in-memory fallback)${NC}"
        return 0
    fi
    
    if check_port $REDIS_PORT; then
        echo -e "  ${GREEN}Redis already running on port $REDIS_PORT${NC}"
        return 0
    fi
    
    # Try Docker
    if command -v docker &> /dev/null; then
        echo "  Starting Redis via Docker..."
        
        # Check if container exists
        if docker ps -a --format "{{.Names}}" | grep -q "^pi-redis-test$"; then
            docker start pi-redis-test &> /dev/null || true
        else
            docker run -d --name pi-redis-test -p ${REDIS_PORT}:6379 redis:7-alpine &> /dev/null || true
        fi
        
        sleep 3
        
        if check_port $REDIS_PORT; then
            echo -e "  ${GREEN}Redis started successfully${NC}"
            STARTED_CONTAINERS+=("pi-redis-test")
            return 0
        fi
    fi
    
    echo -e "  ${YELLOW}Redis not available, tests will use in-memory fallback${NC}"
    return 0
}

start_api_service() {
    if check_port $API_SERVICE_PORT; then
        echo -e "  ${GREEN}API Service already running on port $API_SERVICE_PORT${NC}"
        return 0
    fi
    
    echo "  Starting API Service in background..."
    
    cd "${PROJECT_ROOT}/api_service"
    export PYTHONPATH="${PROJECT_ROOT}"
    
    # Start in background with nohup
    nohup python -m uvicorn app:app --host 0.0.0.0 --port $API_SERVICE_PORT > /tmp/api_service.log 2>&1 &
    local pid=$!
    STARTED_PIDS+=($pid)
    
    cd "${PROJECT_ROOT}"
    
    # Wait for service
    sleep 3
    wait_for_service "${API_SERVICE_URL}/docs" "API Service" $STARTUP_WAIT_SECONDS
}

start_web_service() {
    if check_port $WEB_SERVICE_PORT; then
        echo -e "  ${GREEN}Web Service already running on port $WEB_SERVICE_PORT${NC}"
        return 0
    fi
    
    echo "  Starting Web Service in background..."
    
    cd "${PROJECT_ROOT}/web_service"
    export PYTHONPATH="${PROJECT_ROOT}"
    
    # Start in background with nohup
    nohup python -m uvicorn app:app --host 0.0.0.0 --port $WEB_SERVICE_PORT > /tmp/web_service.log 2>&1 &
    local pid=$!
    STARTED_PIDS+=($pid)
    
    cd "${PROJECT_ROOT}"
    
    # Wait for service
    sleep 3
    wait_for_service "${WEB_SERVICE_URL}/" "Web Service" $STARTUP_WAIT_SECONDS
}

# =============================================================================
# TEST FUNCTIONS
# =============================================================================

test_api_service_health() {
    write_section "API Service Health Tests"
    
    # Test 1: Docs endpoint (no auth)
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" "${API_SERVICE_URL}/docs" 2>/dev/null)
    if [[ "$response" == "200" ]]; then
        write_test_result "API Docs Accessible" "true"
    else
        write_test_result "API Docs Accessible" "false" "HTTP $response"
    fi
    
    # Test 2: Auth endpoint
    response=$(curl -s -X POST "${API_SERVICE_URL}/dev/auth/token" \
        -H "Content-Type: application/json" \
        -d "{\"client_id\": \"${TEST_CLIENT_ID}\", \"client_secret\": \"${TEST_CLIENT_SECRET}\"}" 2>/dev/null)
    
    if echo "$response" | grep -q "access_token"; then
        write_test_result "Token Generation" "true"
        get_auth_token
    else
        write_test_result "Token Generation" "false" "No token in response"
    fi
    
    # Test 3: Invalid credentials
    response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_SERVICE_URL}/dev/auth/token" \
        -H "Content-Type: application/json" \
        -d "{\"client_id\": \"invalid\", \"client_secret\": \"invalid\"}" 2>/dev/null)
    
    if [[ "$response" == "401" ]]; then
        write_test_result "Invalid Credentials Rejected" "true"
    else
        write_test_result "Invalid Credentials Rejected" "false" "Expected 401, got $response"
    fi
    
    # Test 4: Health endpoint with auth
    if [[ -n "$AUTH_TOKEN" ]]; then
        response=$(curl -s "${API_SERVICE_URL}/dev/health" \
            -H "Authorization: Bearer ${AUTH_TOKEN}" 2>/dev/null)
        
        if echo "$response" | grep -q "healthy"; then
            write_test_result "Health Endpoint (Authenticated)" "true"
        else
            write_test_result "Health Endpoint (Authenticated)" "false" "Not healthy"
        fi
    fi
}

test_api_service_redaction() {
    write_section "API Service Redaction Tests"
    
    if [[ -z "$AUTH_TOKEN" ]]; then
        get_auth_token || true
    fi
    
    if [[ -z "$AUTH_TOKEN" ]]; then
        write_test_skipped "All Redaction Tests" "No auth token available"
        return
    fi
    
    # Test 1: Email redaction
    local response
    response=$(curl -s -X POST "${API_SERVICE_URL}/dev/v1/redact" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        -d '{"text": "Contact john.smith@example.com for details"}' 2>/dev/null)
    
    if echo "$response" | grep -q "\[EMAIL\]"; then
        write_test_result "Email Redaction" "true"
    else
        write_test_result "Email Redaction" "false" "No [EMAIL] placeholder"
    fi
    
    # Test 2: Phone redaction
    response=$(curl -s -X POST "${API_SERVICE_URL}/dev/v1/redact" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        -d '{"text": "Call me at 555-123-4567"}' 2>/dev/null)
    
    if echo "$response" | grep -q "\[PHONE\]"; then
        write_test_result "Phone Redaction" "true"
    else
        write_test_result "Phone Redaction" "false" "No [PHONE] placeholder"
    fi
    
    # Test 3: SSN redaction
    response=$(curl -s -X POST "${API_SERVICE_URL}/dev/v1/redact" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        -d '{"text": "SSN: 123-45-6789"}' 2>/dev/null)
    
    if echo "$response" | grep -q "\[SSN\]"; then
        write_test_result "SSN Redaction" "true"
    else
        write_test_result "SSN Redaction" "false" "No [SSN] placeholder"
    fi
    
    # Test 4: Batch redaction
    response=$(curl -s -X POST "${API_SERVICE_URL}/dev/v1/redact/batch" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        -d '{"texts": ["Email: test@example.com", "Phone: 555-111-2222"]}' 2>/dev/null)
    
    if echo "$response" | grep -q "results"; then
        write_test_result "Batch Redaction" "true"
    else
        write_test_result "Batch Redaction" "false" "No results array"
    fi
    
    # Test 5: Models endpoint
    response=$(curl -s "${API_SERVICE_URL}/dev/v1/models" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" 2>/dev/null)
    
    if echo "$response" | grep -q "models"; then
        write_test_result "Models Endpoint" "true"
    else
        write_test_result "Models Endpoint" "false" "No models in response"
    fi
}

test_web_service_health() {
    write_section "Web Service Health Tests"
    
    # Test 1: Home page
    local response
    response=$(curl -s "${WEB_SERVICE_URL}/" 2>/dev/null)
    
    if echo "$response" | grep -qi "html"; then
        write_test_result "Home Page Accessible" "true"
    else
        write_test_result "Home Page Accessible" "false" "No HTML content"
    fi
    
    # Test 2: Health endpoint
    response=$(curl -s "${WEB_SERVICE_URL}/health" 2>/dev/null)
    
    if echo "$response" | grep -q "status"; then
        write_test_result "Health Endpoint" "true"
    else
        write_test_result "Health Endpoint" "false" "No status in response"
    fi
}

test_web_service_redaction() {
    write_section "Web Service Redaction Tests"
    
    # Test 1: Text redaction
    local response
    response=$(curl -s -X POST "${WEB_SERVICE_URL}/api/redact-text" \
        -H "Content-Type: application/json" \
        -d '{"text": "My email is user@example.com", "fast_mode": false}' 2>/dev/null)
    
    if echo "$response" | grep -q "\[EMAIL\]"; then
        write_test_result "Text Redaction (Web)" "true"
    else
        # Try alternate endpoint
        response=$(curl -s -X POST "${WEB_SERVICE_URL}/redact" \
            -d "text=My email is user@example.com" 2>/dev/null)
        
        if echo "$response" | grep -q "\[EMAIL\]"; then
            write_test_result "Text Redaction (Web)" "true"
        else
            write_test_result "Text Redaction (Web)" "false" "No [EMAIL] placeholder"
        fi
    fi
}

test_core_components() {
    write_section "Core Component Tests"
    
    cd "${PROJECT_ROOT}"
    export PYTHONPATH="${PROJECT_ROOT}"
    
    # Test 1: PIRemover import
    if python3 -c "from src.pi_remover.core import PIRemover; print('OK')" 2>/dev/null | grep -q "OK"; then
        write_test_result "PIRemover Import" "true"
    else
        write_test_result "PIRemover Import" "false" "Import failed"
    fi
    
    # Test 2: Security module
    if python3 -c "from security import verify_token, generate_token; print('OK')" 2>/dev/null | grep -q "OK"; then
        write_test_result "Security Module Import" "true"
    else
        write_test_result "Security Module Import" "false" "Import failed"
    fi
    
    # Test 3: Config loader
    if python3 -c "from shared.config_loader import ConfigLoader; print('OK')" 2>/dev/null | grep -q "OK"; then
        write_test_result "Config Loader Import" "true"
    else
        write_test_result "Config Loader Import" "false" "Import failed"
    fi
    
    # Test 4: API Client
    if python3 -c "from web_service.api_client import PIRemoverAPIClient; print('OK')" 2>/dev/null | grep -q "OK"; then
        write_test_result "API Client Import" "true"
    else
        write_test_result "API Client Import" "false" "Import failed"
    fi
    
    # Test 5: Redis client
    if python3 -c "from shared.redis_client import RedisClient; print('OK')" 2>/dev/null | grep -q "OK"; then
        write_test_result "Redis Client Import" "true"
    else
        write_test_result "Redis Client Import" "false" "Import failed"
    fi
}

test_configuration_files() {
    write_section "Configuration File Tests"
    
    local config_files=("api_service.yaml" "web_service.yaml" "clients.yaml" "redis.yaml" "logging.yaml")
    
    for file in "${config_files[@]}"; do
        local file_path="${PROJECT_ROOT}/${CONFIG_PATH}/${file}"
        if [[ -f "$file_path" ]]; then
            if python3 -c "import yaml; yaml.safe_load(open('$file_path')); print('OK')" 2>/dev/null | grep -q "OK"; then
                write_test_result "Config: $file" "true"
            else
                write_test_result "Config: $file" "false" "Invalid YAML"
            fi
        else
            write_test_result "Config: $file" "false" "File not found"
        fi
    done
}

test_pytest_suite() {
    write_section "Pytest Test Suite"
    
    cd "${PROJECT_ROOT}"
    export PYTHONPATH="${PROJECT_ROOT}"
    
    echo -e "  ${CYAN}Running pytest...${NC}"
    
    if python3 -m pytest tests/ -v --tb=short 2>&1; then
        write_test_result "Pytest Suite" "true"
    else
        write_test_result "Pytest Suite" "false" "Some tests failed"
    fi
}

test_integration_tests() {
    write_section "Integration Tests"
    
    cd "${PROJECT_ROOT}"
    export PYTHONPATH="${PROJECT_ROOT}"
    export API_SERVICE_URL="${API_SERVICE_URL}"
    export WEB_SERVICE_URL="${WEB_SERVICE_URL}"
    
    local test_file="${PROJECT_ROOT}/tests/test_service_integration.py"
    
    if [[ -f "$test_file" ]]; then
        echo -e "  ${CYAN}Running integration tests...${NC}"
        
        if python3 -m pytest "$test_file" -v --tb=short 2>&1; then
            write_test_result "Service Integration Tests" "true"
        else
            write_test_result "Service Integration Tests" "false" "Some tests failed"
        fi
    else
        write_test_skipped "Service Integration Tests" "Test file not found"
    fi
}

# =============================================================================
# CLEANUP FUNCTION
# =============================================================================

cleanup() {
    write_section "Cleanup"
    
    # Stop processes
    for pid in "${STARTED_PIDS[@]}"; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "  Stopping process $pid..."
            kill $pid 2>/dev/null || true
        fi
    done
    
    # Stop Docker containers
    for container in "${STARTED_CONTAINERS[@]}"; do
        echo "  Stopping container $container..."
        docker stop $container 2>/dev/null || true
    done
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    write_banner "PI Remover Comprehensive Test Suite v2.9.0"
    
    echo "Configuration:"
    echo "  Project Root: ${PROJECT_ROOT}"
    echo "  Config Path:  ${CONFIG_PATH}"
    echo "  API Service:  ${API_SERVICE_URL}"
    echo "  Web Service:  ${WEB_SERVICE_URL}"
    echo ""
    
    cd "${PROJECT_ROOT}"
    
    if [[ "$TEST_ONLY" != "true" ]]; then
        # =============================================================================
        # START SERVICES
        # =============================================================================
        
        write_banner "Starting Services"
        
        echo -e "${CYAN}Starting Redis...${NC}"
        start_redis_service
        
        echo -e "${CYAN}Starting API Service...${NC}"
        if ! start_api_service; then
            echo -e "${RED}Failed to start API Service${NC}"
            cleanup
            exit 1
        fi
        
        echo -e "${CYAN}Starting Web Service...${NC}"
        if ! start_web_service; then
            echo -e "${RED}Failed to start Web Service${NC}"
            cleanup
            exit 1
        fi
        
        echo ""
        echo -e "${GREEN}All services started successfully!${NC}"
        sleep 3
    else
        echo -e "${YELLOW}TestOnly mode - assuming services are already running${NC}"
    fi
    
    # =============================================================================
    # RUN TESTS
    # =============================================================================
    
    write_banner "Running Tests"
    
    test_core_components
    test_configuration_files
    test_api_service_health
    test_api_service_redaction
    test_web_service_health
    test_web_service_redaction
    test_pytest_suite
    test_integration_tests
    
    # =============================================================================
    # RESULTS SUMMARY
    # =============================================================================
    
    write_banner "Test Results Summary"
    
    local total=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))
    local pass_rate=0
    if [[ $((TESTS_PASSED + TESTS_FAILED)) -gt 0 ]]; then
        pass_rate=$(echo "scale=1; ($TESTS_PASSED * 100) / ($TESTS_PASSED + $TESTS_FAILED)" | bc)
    fi
    
    echo "  Total Tests: $total"
    echo -e "  Passed:      ${GREEN}${TESTS_PASSED}${NC}"
    if [[ $TESTS_FAILED -gt 0 ]]; then
        echo -e "  Failed:      ${RED}${TESTS_FAILED}${NC}"
    else
        echo -e "  Failed:      ${GREEN}${TESTS_FAILED}${NC}"
    fi
    echo -e "  Skipped:     ${YELLOW}${TESTS_SKIPPED}${NC}"
    echo "  Pass Rate:   ${pass_rate}%"
    echo ""
    
    # =============================================================================
    # CLEANUP
    # =============================================================================
    
    if [[ "$SKIP_CLEANUP" != "true" && "$TEST_ONLY" != "true" ]]; then
        cleanup
    else
        echo ""
        echo -e "${YELLOW}Services left running. To stop manually:${NC}"
        echo "  - Kill API service: kill ${STARTED_PIDS[0]:-N/A}"
        echo "  - Kill Web service: kill ${STARTED_PIDS[1]:-N/A}"
        echo "  - Stop Redis: docker stop pi-redis-test"
    fi
    
    # Exit with appropriate code
    if [[ $TESTS_FAILED -gt 0 ]]; then
        exit 1
    else
        echo ""
        echo -e "${GREEN}All tests completed successfully!${NC}"
        exit 0
    fi
}

# Trap for cleanup on exit
trap cleanup EXIT

# Run main
main
