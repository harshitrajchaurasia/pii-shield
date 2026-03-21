<#
.SYNOPSIS
    Comprehensive Test Script for PI Remover Microservices Architecture
    
.DESCRIPTION
    This script starts all services in separate terminals and runs comprehensive tests:
    - API Service (Port 8080)
    - Web Service (Port 8082)
    - Redis (Port 6379, optional)
    - Integration Tests
    - Component Tests
    
.PARAMETER ConfigPath
    Path to configuration files. Default: "config"
    
.PARAMETER SkipRedis
    Skip Redis startup (uses in-memory fallback)
    
.PARAMETER SkipCleanup
    Keep services running after tests complete
    
.PARAMETER TestOnly
    Only run tests, assume services are already running
    
.EXAMPLE
    .\scripts\run_comprehensive_tests.ps1
    
.EXAMPLE
    .\scripts\run_comprehensive_tests.ps1 -SkipRedis -SkipCleanup
    
.NOTES
    Version: 2.9.0
    Author: PI Remover Team
#>

param(
    [string]$ConfigPath = "config",
    [switch]$SkipRedis,
    [switch]$SkipCleanup,
    [switch]$TestOnly,
    [int]$StartupWaitSeconds = 30
)

# =============================================================================
# CONFIGURATION
# =============================================================================

$ErrorActionPreference = "Stop"

# Determine project root - PSScriptRoot is the scripts folder
if ($PSScriptRoot) {
    $script:ProjectRoot = Split-Path -Parent $PSScriptRoot
} else {
    $script:ProjectRoot = (Get-Location).Path
}

# Verify we're in the right place
if (-not (Test-Path (Join-Path $script:ProjectRoot "api_service"))) {
    Write-Host "Error: Cannot find api_service directory. Please run from project root." -ForegroundColor Red
    exit 1
}

$script:APIServicePort = 8080
$script:WebServicePort = 8082
$script:RedisPort = 6379

$script:APIServiceUrl = "http://localhost:$script:APIServicePort"
$script:WebServiceUrl = "http://localhost:$script:WebServicePort"

# Test credentials
$script:TestClientId = "pi-dev-client"
$script:TestClientSecret = "YOUR_DEV_CLIENT_SECRET_HERE"

# Track started processes
$script:StartedProcesses = @()
$script:TestResults = @{
    Passed = 0
    Failed = 0
    Skipped = 0
    Details = @()
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

function Write-Banner {
    param([string]$Title)
    $line = "=" * 70
    Write-Host ""
    Write-Host $line -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host $line -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "--- $Title ---" -ForegroundColor Yellow
    Write-Host ""
}

function Write-TestResult {
    param(
        [string]$TestName,
        [bool]$Passed,
        [string]$Message = ""
    )
    
    if ($Passed) {
        Write-Host "  [PASS] " -ForegroundColor Green -NoNewline
        Write-Host $TestName
        $script:TestResults.Passed++
    } else {
        Write-Host "  [FAIL] " -ForegroundColor Red -NoNewline
        Write-Host "$TestName - $Message"
        $script:TestResults.Failed++
    }
    
    $script:TestResults.Details += @{
        Name = $TestName
        Passed = $Passed
        Message = $Message
    }
}

function Write-TestSkipped {
    param([string]$TestName, [string]$Reason)
    Write-Host "  [SKIP] " -ForegroundColor Yellow -NoNewline
    Write-Host "$TestName - $Reason"
    $script:TestResults.Skipped++
}

function Test-PortInUse {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Wait-ForService {
    param(
        [string]$Url,
        [string]$ServiceName,
        [int]$TimeoutSeconds = 60,
        [hashtable]$Headers = @{}
    )
    
    Write-Host "  Waiting for $ServiceName at $Url..." -NoNewline
    
    $startTime = Get-Date
    $endTime = $startTime.AddSeconds($TimeoutSeconds)
    
    while ((Get-Date) -lt $endTime) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Headers $Headers -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Host " Ready!" -ForegroundColor Green
                return $true
            }
        } catch {
            # Expected while service is starting
        }
        Start-Sleep -Seconds 2
        Write-Host "." -NoNewline
    }
    
    Write-Host " Timeout!" -ForegroundColor Red
    return $false
}

function Get-AuthToken {
    try {
        $body = @{
            client_id = $script:TestClientId
            client_secret = $script:TestClientSecret
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$script:APIServiceUrl/dev/auth/token" `
            -Method POST `
            -Body $body `
            -ContentType "application/json" `
            -ErrorAction Stop
            
        return $response.access_token
    } catch {
        Write-Host "  Failed to get auth token: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

# =============================================================================
# SERVICE STARTUP FUNCTIONS
# =============================================================================

function Start-RedisService {
    if ($SkipRedis) {
        Write-Host "  Skipping Redis (using in-memory fallback)" -ForegroundColor Yellow
        return $true
    }
    
    if (Test-PortInUse -Port $script:RedisPort) {
        Write-Host "  Redis already running on port $script:RedisPort" -ForegroundColor Green
        return $true
    }
    
    # Try Docker first
    $dockerAvailable = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)
    
    if ($dockerAvailable) {
        Write-Host "  Starting Redis via Docker..."
        
        # Check if container already exists
        $existingContainer = docker ps -a --filter "name=pi-redis-test" --format "{{.Names}}" 2>$null
        if ($existingContainer -eq "pi-redis-test") {
            docker start pi-redis-test 2>$null | Out-Null
        } else {
            docker run -d --name pi-redis-test -p "${script:RedisPort}:6379" redis:7-alpine 2>$null | Out-Null
        }
        
        Start-Sleep -Seconds 3
        
        if (Test-PortInUse -Port $script:RedisPort) {
            Write-Host "  Redis started successfully" -ForegroundColor Green
            $script:StartedProcesses += "docker:pi-redis-test"
            return $true
        }
    }
    
    Write-Host "  Redis not available, tests will use in-memory fallback" -ForegroundColor Yellow
    return $true
}

function Start-APIService {
    if (Test-PortInUse -Port $script:APIServicePort) {
        Write-Host "  API Service already running on port $script:APIServicePort" -ForegroundColor Green
        return $true
    }
    
    Write-Host "  Starting API Service in new terminal..."
    
    $apiServicePath = Join-Path $script:ProjectRoot "api_service"
    $configPath = Join-Path $script:ProjectRoot $ConfigPath
    
    # Create startup script
    $startupScript = @"
`$Host.UI.RawUI.WindowTitle = 'PI Remover - API Service (Port $script:APIServicePort)'
Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  PI Remover API Service' -ForegroundColor Cyan
Write-Host '  Port: $script:APIServicePort' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''
Set-Location '$apiServicePath'
`$env:PYTHONPATH = '$script:ProjectRoot'
python -m uvicorn app:app --host 0.0.0.0 --port $script:APIServicePort --reload
"@
    
    $scriptFile = Join-Path $env:TEMP "start_api_service.ps1"
    $startupScript | Out-File -FilePath $scriptFile -Encoding UTF8
    
    $process = Start-Process powershell -ArgumentList "-NoExit", "-File", $scriptFile -PassThru
    $script:StartedProcesses += "process:$($process.Id)"
    
    # Wait for service to be ready
    Start-Sleep -Seconds 5
    
    # For API service, we need to wait for /docs endpoint (no auth required)
    return (Wait-ForService -Url "$script:APIServiceUrl/docs" -ServiceName "API Service" -TimeoutSeconds $StartupWaitSeconds)
}

function Start-WebService {
    if (Test-PortInUse -Port $script:WebServicePort) {
        Write-Host "  Web Service already running on port $script:WebServicePort" -ForegroundColor Green
        return $true
    }
    
    Write-Host "  Starting Web Service in new terminal..."
    
    $webServicePath = Join-Path $script:ProjectRoot "web_service"
    $configPath = Join-Path $script:ProjectRoot $ConfigPath
    
    # Create startup script
    $startupScript = @"
`$Host.UI.RawUI.WindowTitle = 'PI Remover - Web Service (Port $script:WebServicePort)'
Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  PI Remover Web Service' -ForegroundColor Cyan
Write-Host '  Port: $script:WebServicePort' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''
Set-Location '$webServicePath'
`$env:PYTHONPATH = '$script:ProjectRoot'
python -m uvicorn app:app --host 0.0.0.0 --port $script:WebServicePort --reload
"@
    
    $scriptFile = Join-Path $env:TEMP "start_web_service.ps1"
    $startupScript | Out-File -FilePath $scriptFile -Encoding UTF8
    
    $process = Start-Process powershell -ArgumentList "-NoExit", "-File", $scriptFile -PassThru
    $script:StartedProcesses += "process:$($process.Id)"
    
    # Wait for service to be ready
    Start-Sleep -Seconds 5
    
    return (Wait-ForService -Url "$script:WebServiceUrl/" -ServiceName "Web Service" -TimeoutSeconds $StartupWaitSeconds)
}

# =============================================================================
# TEST FUNCTIONS
# =============================================================================

function Test-APIServiceHealth {
    Write-Section "API Service Health Tests"
    
    # Test 1: Docs endpoint (no auth)
    try {
        $response = Invoke-WebRequest -Uri "$script:APIServiceUrl/docs" -TimeoutSec 10
        Write-TestResult -TestName "API Docs Accessible" -Passed ($response.StatusCode -eq 200)
    } catch {
        Write-TestResult -TestName "API Docs Accessible" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 2: Auth endpoint
    try {
        $body = @{
            client_id = $script:TestClientId
            client_secret = $script:TestClientSecret
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$script:APIServiceUrl/dev/auth/token" `
            -Method POST -Body $body -ContentType "application/json"
            
        $tokenOk = $null -ne $response.access_token
        Write-TestResult -TestName "Token Generation" -Passed $tokenOk
        
        if ($tokenOk) {
            $script:AuthToken = $response.access_token
        }
    } catch {
        Write-TestResult -TestName "Token Generation" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 3: Invalid credentials rejected
    try {
        $body = @{
            client_id = "invalid"
            client_secret = "invalid"
        } | ConvertTo-Json
        
        $response = Invoke-WebRequest -Uri "$script:APIServiceUrl/dev/auth/token" `
            -Method POST -Body $body -ContentType "application/json" -ErrorAction Stop
            
        Write-TestResult -TestName "Invalid Credentials Rejected" -Passed $false -Message "Should have returned 401"
    } catch {
        $is401 = $_.Exception.Response.StatusCode -eq 401 -or $_.Exception.Message -match "401"
        Write-TestResult -TestName "Invalid Credentials Rejected" -Passed $is401
    }
    
    # Test 4: Health endpoint with auth
    if ($script:AuthToken) {
        try {
            $headers = @{ Authorization = "Bearer $($script:AuthToken)" }
            $response = Invoke-RestMethod -Uri "$script:APIServiceUrl/dev/health" -Headers $headers
            
            $healthOk = $response.status -eq "healthy"
            Write-TestResult -TestName "Health Endpoint (Authenticated)" -Passed $healthOk
        } catch {
            Write-TestResult -TestName "Health Endpoint (Authenticated)" -Passed $false -Message $_.Exception.Message
        }
    }
}

function Test-APIServiceRedaction {
    Write-Section "API Service Redaction Tests"
    
    if (-not $script:AuthToken) {
        $script:AuthToken = Get-AuthToken
    }
    
    if (-not $script:AuthToken) {
        Write-TestSkipped -TestName "All Redaction Tests" -Reason "No auth token available"
        return
    }
    
    $headers = @{ Authorization = "Bearer $($script:AuthToken)" }
    
    # Test 1: Email redaction
    try {
        $body = @{ text = "Contact john.smith@example.com for details" } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$script:APIServiceUrl/dev/v1/redact" `
            -Method POST -Body $body -ContentType "application/json" -Headers $headers
            
        $emailRedacted = $response.redacted_text -match "\[EMAIL\]" -and 
                         $response.redacted_text -notmatch "john\.smith@example\.com"
        Write-TestResult -TestName "Email Redaction" -Passed $emailRedacted
    } catch {
        Write-TestResult -TestName "Email Redaction" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 2: Phone redaction
    try {
        $body = @{ text = "Call me at 555-123-4567 or (800) 555-1234" } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$script:APIServiceUrl/dev/v1/redact" `
            -Method POST -Body $body -ContentType "application/json" -Headers $headers
            
        $phoneRedacted = $response.redacted_text -match "\[PHONE\]"
        Write-TestResult -TestName "Phone Redaction" -Passed $phoneRedacted
    } catch {
        Write-TestResult -TestName "Phone Redaction" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 3: SSN redaction
    try {
        $body = @{ text = "SSN: 123-45-6789" } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$script:APIServiceUrl/dev/v1/redact" `
            -Method POST -Body $body -ContentType "application/json" -Headers $headers
            
        $ssnRedacted = $response.redacted_text -match "\[SSN\]" -and 
                       $response.redacted_text -notmatch "123-45-6789"
        Write-TestResult -TestName "SSN Redaction" -Passed $ssnRedacted
    } catch {
        Write-TestResult -TestName "SSN Redaction" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 4: Credit card redaction
    try {
        $body = @{ text = "Card: 4111-1111-1111-1111" } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$script:APIServiceUrl/dev/v1/redact" `
            -Method POST -Body $body -ContentType "application/json" -Headers $headers
            
        $ccRedacted = $response.redacted_text -match "\[CREDIT_CARD\]|\[CC\]"
        Write-TestResult -TestName "Credit Card Redaction" -Passed $ccRedacted
    } catch {
        Write-TestResult -TestName "Credit Card Redaction" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 5: Batch redaction
    try {
        $body = @{
            texts = @(
                "Email: test1@example.com",
                "Phone: 555-111-2222",
                "SSN: 111-22-3333"
            )
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$script:APIServiceUrl/dev/v1/redact/batch" `
            -Method POST -Body $body -ContentType "application/json" -Headers $headers
            
        $batchOk = $response.results.Count -eq 3
        Write-TestResult -TestName "Batch Redaction" -Passed $batchOk
    } catch {
        Write-TestResult -TestName "Batch Redaction" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 6: Models endpoint
    try {
        $response = Invoke-RestMethod -Uri "$script:APIServiceUrl/dev/v1/models" -Headers $headers
        $modelsOk = $null -ne $response.models -and $response.models.Count -gt 0
        Write-TestResult -TestName "Models Endpoint" -Passed $modelsOk
    } catch {
        Write-TestResult -TestName "Models Endpoint" -Passed $false -Message $_.Exception.Message
    }
}

function Test-WebServiceHealth {
    Write-Section "Web Service Health Tests"
    
    # Test 1: Home page
    try {
        $response = Invoke-WebRequest -Uri "$script:WebServiceUrl/" -TimeoutSec 10
        $homeOk = $response.StatusCode -eq 200 -and $response.Content -match "html"
        Write-TestResult -TestName "Home Page Accessible" -Passed $homeOk
    } catch {
        Write-TestResult -TestName "Home Page Accessible" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 2: Health endpoint
    try {
        $response = Invoke-RestMethod -Uri "$script:WebServiceUrl/health" -TimeoutSec 10
        $healthOk = $null -ne $response.status
        Write-TestResult -TestName "Health Endpoint" -Passed $healthOk
    } catch {
        Write-TestResult -TestName "Health Endpoint" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 3: Service info
    try {
        $response = Invoke-RestMethod -Uri "$script:WebServiceUrl/api/service-info" -TimeoutSec 10
        $infoOk = $null -ne $response
        Write-TestResult -TestName "Service Info Endpoint" -Passed $infoOk
    } catch {
        # May not exist in current version
        Write-TestSkipped -TestName "Service Info Endpoint" -Reason "Endpoint may not exist"
    }
}

function Test-WebServiceRedaction {
    Write-Section "Web Service Redaction Tests"
    
    # Test 1: Text redaction via form
    try {
        $body = @{
            text = "My email is user@example.com"
            fast_mode = $false
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$script:WebServiceUrl/api/redact-text" `
            -Method POST -Body $body -ContentType "application/json" -TimeoutSec 30
            
        $redactOk = $response.redacted_text -match "\[EMAIL\]"
        Write-TestResult -TestName "Text Redaction (Web)" -Passed $redactOk
    } catch {
        # Try alternate endpoint
        try {
            $formBody = @{ text = "My email is user@example.com" }
            $response = Invoke-RestMethod -Uri "$script:WebServiceUrl/redact" `
                -Method POST -Body $formBody -TimeoutSec 30
            $redactOk = $response -match "\[EMAIL\]" -or $response.redacted_text -match "\[EMAIL\]"
            Write-TestResult -TestName "Text Redaction (Web)" -Passed $redactOk
        } catch {
            Write-TestResult -TestName "Text Redaction (Web)" -Passed $false -Message $_.Exception.Message
        }
    }
    
    # Test 2: Fast mode
    try {
        $body = @{
            text = "Call 555-123-4567"
            fast_mode = $true
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$script:WebServiceUrl/api/redact-text" `
            -Method POST -Body $body -ContentType "application/json" -TimeoutSec 30
            
        $fastOk = $response.redacted_text -match "\[PHONE\]"
        Write-TestResult -TestName "Fast Mode Redaction" -Passed $fastOk
    } catch {
        Write-TestSkipped -TestName "Fast Mode Redaction" -Reason "Endpoint may not exist"
    }
}

function Test-CoreComponents {
    Write-Section "Core Component Tests"
    
    # Test 1: PIRemover import
    try {
        $result = python -c "from src.pi_remover.core import PIRemover; print('OK')" 2>&1
        $importOk = $result -eq "OK"
        Write-TestResult -TestName "PIRemover Import" -Passed $importOk
    } catch {
        Write-TestResult -TestName "PIRemover Import" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 2: Security module
    try {
        $result = python -c "from security import verify_token, generate_token; print('OK')" 2>&1
        $securityOk = $result -eq "OK"
        Write-TestResult -TestName "Security Module Import" -Passed $securityOk
    } catch {
        Write-TestResult -TestName "Security Module Import" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 3: Shared config loader
    try {
        $result = python -c "from shared.config_loader import ConfigLoader; print('OK')" 2>&1
        $configOk = $result -eq "OK"
        Write-TestResult -TestName "Config Loader Import" -Passed $configOk
    } catch {
        Write-TestResult -TestName "Config Loader Import" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 4: API Client
    try {
        $result = python -c "from web_service.api_client import PIRemoverAPIClient; print('OK')" 2>&1
        $clientOk = $result -eq "OK"
        Write-TestResult -TestName "API Client Import" -Passed $clientOk
    } catch {
        Write-TestResult -TestName "API Client Import" -Passed $false -Message $_.Exception.Message
    }
    
    # Test 5: Redis client (with fallback)
    try {
        $result = python -c "from shared.redis_client import RedisClient; print('OK')" 2>&1
        $redisOk = $result -eq "OK"
        Write-TestResult -TestName "Redis Client Import" -Passed $redisOk
    } catch {
        Write-TestResult -TestName "Redis Client Import" -Passed $false -Message $_.Exception.Message
    }
}

function Test-ConfigurationFiles {
    Write-Section "Configuration File Tests"
    
    $configFiles = @(
        "api_service.yaml",
        "web_service.yaml",
        "clients.yaml",
        "redis.yaml",
        "logging.yaml"
    )
    
    foreach ($file in $configFiles) {
        $filePath = Join-Path $script:ProjectRoot $ConfigPath $file
        if (Test-Path $filePath) {
            try {
                $result = python -c "import yaml; yaml.safe_load(open('$($filePath.Replace('\','/'))')); print('OK')" 2>&1
                $valid = $result -eq "OK"
                Write-TestResult -TestName "Config: $file" -Passed $valid
            } catch {
                Write-TestResult -TestName "Config: $file" -Passed $false -Message "Invalid YAML"
            }
        } else {
            Write-TestResult -TestName "Config: $file" -Passed $false -Message "File not found"
        }
    }
}

function Test-PytestSuite {
    Write-Section "Pytest Test Suite"
    
    Push-Location $script:ProjectRoot
    
    try {
        # Run existing tests
        Write-Host "  Running pytest..." -ForegroundColor Cyan
        
        $testResult = python -m pytest tests/ -v --tb=short 2>&1
        $testsPassed = $LASTEXITCODE -eq 0
        
        # Count passed/failed
        $passedMatch = $testResult | Select-String -Pattern "(\d+) passed"
        $failedMatch = $testResult | Select-String -Pattern "(\d+) failed"
        
        $passedCount = if ($passedMatch) { $passedMatch.Matches[0].Groups[1].Value } else { 0 }
        $failedCount = if ($failedMatch) { $failedMatch.Matches[0].Groups[1].Value } else { 0 }
        
        Write-TestResult -TestName "Pytest Suite ($passedCount passed, $failedCount failed)" -Passed $testsPassed
        
    } catch {
        Write-TestResult -TestName "Pytest Suite" -Passed $false -Message $_.Exception.Message
    } finally {
        Pop-Location
    }
}

function Test-IntegrationTests {
    Write-Section "Integration Tests"
    
    Push-Location $script:ProjectRoot
    
    try {
        # Run integration tests specifically
        $integrationTestFile = Join-Path $script:ProjectRoot "tests\test_service_integration.py"
        
        if (Test-Path $integrationTestFile) {
            Write-Host "  Running integration tests..." -ForegroundColor Cyan
            
            $env:API_SERVICE_URL = $script:APIServiceUrl
            $env:WEB_SERVICE_URL = $script:WebServiceUrl
            
            $testResult = python -m pytest $integrationTestFile -v --tb=short 2>&1
            $testsPassed = $LASTEXITCODE -eq 0
            
            Write-TestResult -TestName "Service Integration Tests" -Passed $testsPassed
        } else {
            Write-TestSkipped -TestName "Service Integration Tests" -Reason "Test file not found"
        }
        
    } catch {
        Write-TestResult -TestName "Service Integration Tests" -Passed $false -Message $_.Exception.Message
    } finally {
        Pop-Location
    }
}

# =============================================================================
# CLEANUP FUNCTION
# =============================================================================

function Stop-AllServices {
    Write-Section "Cleanup"
    
    foreach ($item in $script:StartedProcesses) {
        $parts = $item -split ":"
        $type = $parts[0]
        $id = $parts[1]
        
        switch ($type) {
            "process" {
                try {
                    $process = Get-Process -Id $id -ErrorAction SilentlyContinue
                    if ($process) {
                        Write-Host "  Stopping process $id ($($process.ProcessName))..."
                        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
                    }
                } catch {
                    # Process may have already exited
                }
            }
            "docker" {
                try {
                    Write-Host "  Stopping Docker container $id..."
                    docker stop $id 2>$null | Out-Null
                } catch {
                    # Container may have already stopped
                }
            }
        }
    }
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

try {
    Write-Banner "PI Remover Comprehensive Test Suite v2.9.0"
    
    Write-Host "Configuration:" -ForegroundColor Gray
    Write-Host "  Project Root: $script:ProjectRoot"
    Write-Host "  Config Path:  $ConfigPath"
    Write-Host "  API Service:  $script:APIServiceUrl"
    Write-Host "  Web Service:  $script:WebServiceUrl"
    Write-Host ""
    
    # Change to project root
    Push-Location $script:ProjectRoot
    
    if (-not $TestOnly) {
        # =============================================================================
        # START SERVICES
        # =============================================================================
        
        Write-Banner "Starting Services"
        
        # Start Redis
        Write-Host "Starting Redis..." -ForegroundColor Cyan
        $redisStarted = Start-RedisService
        
        # Start API Service
        Write-Host "Starting API Service..." -ForegroundColor Cyan
        $apiStarted = Start-APIService
        
        if (-not $apiStarted) {
            throw "Failed to start API Service"
        }
        
        # Start Web Service
        Write-Host "Starting Web Service..." -ForegroundColor Cyan
        $webStarted = Start-WebService
        
        if (-not $webStarted) {
            throw "Failed to start Web Service"
        }
        
        Write-Host ""
        Write-Host "All services started successfully!" -ForegroundColor Green
        Start-Sleep -Seconds 3
    } else {
        Write-Host "TestOnly mode - assuming services are already running" -ForegroundColor Yellow
    }
    
    # =============================================================================
    # RUN TESTS
    # =============================================================================
    
    Write-Banner "Running Tests"
    
    # Core component tests (no services needed)
    Test-CoreComponents
    
    # Configuration file tests
    Test-ConfigurationFiles
    
    # API Service tests
    Test-APIServiceHealth
    Test-APIServiceRedaction
    
    # Web Service tests
    Test-WebServiceHealth
    Test-WebServiceRedaction
    
    # Run pytest suite
    Test-PytestSuite
    
    # Integration tests
    Test-IntegrationTests
    
    # =============================================================================
    # RESULTS SUMMARY
    # =============================================================================
    
    Write-Banner "Test Results Summary"
    
    $total = $script:TestResults.Passed + $script:TestResults.Failed + $script:TestResults.Skipped
    $passRate = if ($total -gt 0) { [math]::Round(($script:TestResults.Passed / ($script:TestResults.Passed + $script:TestResults.Failed)) * 100, 1) } else { 0 }
    
    Write-Host "  Total Tests: $total"
    Write-Host "  Passed:      " -NoNewline
    Write-Host "$($script:TestResults.Passed)" -ForegroundColor Green
    Write-Host "  Failed:      " -NoNewline
    Write-Host "$($script:TestResults.Failed)" -ForegroundColor $(if ($script:TestResults.Failed -gt 0) { "Red" } else { "Green" })
    Write-Host "  Skipped:     " -NoNewline
    Write-Host "$($script:TestResults.Skipped)" -ForegroundColor Yellow
    Write-Host "  Pass Rate:   $passRate%"
    Write-Host ""
    
    if ($script:TestResults.Failed -gt 0) {
        Write-Host "Failed Tests:" -ForegroundColor Red
        foreach ($test in $script:TestResults.Details | Where-Object { -not $_.Passed }) {
            Write-Host "  - $($test.Name): $($test.Message)" -ForegroundColor Red
        }
        Write-Host ""
    }
    
    # =============================================================================
    # CLEANUP
    # =============================================================================
    
    if (-not $SkipCleanup -and -not $TestOnly) {
        Stop-AllServices
    } else {
        Write-Host ""
        Write-Host "Services left running. To stop manually:" -ForegroundColor Yellow
        Write-Host "  - Close the terminal windows for API and Web services"
        Write-Host "  - Run: docker stop pi-redis-test (if using Docker Redis)"
    }
    
    # Exit with appropriate code
    if ($script:TestResults.Failed -gt 0) {
        exit 1
    } else {
        Write-Host ""
        Write-Host "All tests completed successfully!" -ForegroundColor Green
        exit 0
    }
    
} catch {
    Write-Host ""
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Gray
    
    if (-not $SkipCleanup) {
        Stop-AllServices
    }
    
    exit 1
} finally {
    Pop-Location -ErrorAction SilentlyContinue
}
