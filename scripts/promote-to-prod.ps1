<#
.SYNOPSIS
    Promote DEV to PRODUCTION environment.

.DESCRIPTION
    This script guides through the promotion process from DEV to PROD.
    It includes pre-flight checks, testing, and safe deployment steps.

.PARAMETER SkipTests
    Skip running tests before promotion (not recommended).

.PARAMETER SkipConfirmation
    Skip the production deployment confirmation prompt.

.EXAMPLE
    .\promote-to-prod.ps1
    
.EXAMPLE
    .\promote-to-prod.ps1 -SkipTests
#>

[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipConfirmation
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DockerDir = Join-Path $ProjectRoot "docker"

# Banner
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           PI REMOVER - PROMOTION: DEV → PROD                  ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step tracking
$currentStep = 0
$totalSteps = 6

function Write-Step {
    param([string]$Message)
    $script:currentStep++
    Write-Host ""
    Write-Host "[$script:currentStep/$totalSteps] $Message" -ForegroundColor Green
    Write-Host ("-" * 60) -ForegroundColor DarkGray
}

# =========================================================================
# STEP 1: Pre-flight Checks
# =========================================================================
Write-Step "Pre-flight Checks"

# Check Docker is running
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is not running"
    }
    Write-Host "  ✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check environment files
$prodEnvFile = Join-Path $DockerDir ".env.prod"
if (-not (Test-Path $prodEnvFile)) {
    Write-Host "  ✗ Production environment file not found: $prodEnvFile" -ForegroundColor Red
    Write-Host ""
    Write-Host "  To fix:" -ForegroundColor Yellow
    Write-Host "    cp docker\.env.prod.template docker\.env.prod" -ForegroundColor White
    Write-Host "    # Then edit .env.prod with production secrets" -ForegroundColor White
    exit 1
}
Write-Host "  ✓ Production environment file exists" -ForegroundColor Green

# Validate prod env file
$envContent = Get-Content $prodEnvFile -Raw
if ($envContent -match "REPLACE_WITH") {
    Write-Host "  ✗ Production environment file contains unconfigured secrets" -ForegroundColor Red
    Write-Host "    Please update all 'REPLACE_WITH...' placeholders in .env.prod" -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✓ Production secrets configured" -ForegroundColor Green

# Check if DEV is running
$devContainers = docker ps --filter "label=environment=development" --format "{{.Names}}" 2>$null
if (-not $devContainers) {
    Write-Host "  ⚠ DEV environment is not running" -ForegroundColor Yellow
    Write-Host "    Consider running deploy-dev.ps1 first to test changes" -ForegroundColor DarkGray
} else {
    Write-Host "  ✓ DEV environment is running" -ForegroundColor Green
}

# =========================================================================
# STEP 2: Run Tests
# =========================================================================
Write-Step "Running Tests"

if ($SkipTests) {
    Write-Host "  ⚠ Tests skipped (not recommended for production)" -ForegroundColor Yellow
} else {
    Write-Host "  Running pytest..." -ForegroundColor Cyan
    
    Push-Location $ProjectRoot
    try {
        $testResult = python -m pytest tests/ -v --tb=short 2>&1
        $testExitCode = $LASTEXITCODE
        
        if ($testExitCode -eq 0) {
            Write-Host "  ✓ All tests passed" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host $testResult
            Write-Host ""
            Write-Host "  ✗ Tests failed!" -ForegroundColor Red
            Write-Host "    Fix the failing tests before promoting to production." -ForegroundColor Yellow
            exit 1
        }
    } finally {
        Pop-Location
    }
}

# =========================================================================
# STEP 3: Test DEV Health (if running)
# =========================================================================
Write-Step "Testing DEV Environment Health"

if ($devContainers) {
    try {
        Write-Host "  Testing API Gateway (http://localhost:8080/dev/health)..." -ForegroundColor Cyan
        $response = Invoke-WebRequest -Uri "http://localhost:8080/dev/health" -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "  ✓ DEV API Gateway is healthy" -ForegroundColor Green
        }
    } catch {
        Write-Host "  ⚠ DEV API Gateway health check failed: $_" -ForegroundColor Yellow
    }
    
    try {
        Write-Host "  Testing Web Service (http://localhost:8082/health)..." -ForegroundColor Cyan
        $response = Invoke-WebRequest -Uri "http://localhost:8082/health" -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "  ✓ DEV Web Service is healthy" -ForegroundColor Green
        }
    } catch {
        Write-Host "  ⚠ DEV Web Service health check failed: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠ DEV not running - skipping health checks" -ForegroundColor Yellow
}

# =========================================================================
# STEP 4: Confirmation
# =========================================================================
Write-Step "Confirmation"

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║               READY TO PROMOTE TO PRODUCTION                  ║" -ForegroundColor Yellow
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
Write-Host "This will:" -ForegroundColor Cyan
Write-Host "  • Stop existing production containers (if any)" -ForegroundColor White
Write-Host "  • Build fresh Docker images" -ForegroundColor White
Write-Host "  • Deploy to production ports (9080/9082)" -ForegroundColor White
Write-Host "  • Run health checks" -ForegroundColor White
Write-Host ""

if (-not $SkipConfirmation) {
    $confirmation = Read-Host "Type 'PROMOTE' to deploy to production"
    if ($confirmation -ne "PROMOTE") {
        Write-Host ""
        Write-Host "Promotion cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# =========================================================================
# STEP 5: Deploy to Production
# =========================================================================
Write-Step "Deploying to Production"

$deployScript = Join-Path $ScriptDir "deploy-prod.ps1"
& $deployScript -Build -SkipConfirmation

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ✗ Production deployment failed!" -ForegroundColor Red
    exit 1
}

# =========================================================================
# STEP 6: Post-Deployment Verification
# =========================================================================
Write-Step "Post-Deployment Verification"

Write-Host "  Waiting for services to stabilize..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

$allHealthy = $true

# Test production endpoints
try {
    $response = Invoke-WebRequest -Uri "http://localhost:9080/prod/health" -TimeoutSec 10 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✓ PROD API Gateway: HEALTHY" -ForegroundColor Green
    }
} catch {
    Write-Host "  ✗ PROD API Gateway: UNHEALTHY" -ForegroundColor Red
    $allHealthy = $false
}

try {
    $response = Invoke-WebRequest -Uri "http://localhost:9082/health" -TimeoutSec 10 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✓ PROD Web Service: HEALTHY" -ForegroundColor Green
    }
} catch {
    Write-Host "  ✗ PROD Web Service: UNHEALTHY" -ForegroundColor Red
    $allHealthy = $false
}

# Final status
Write-Host ""
if ($allHealthy) {
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║              PROMOTION TO PRODUCTION SUCCESSFUL               ║" -ForegroundColor Green
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "Production services are now live:" -ForegroundColor Cyan
    Write-Host "  • API Gateway:  http://localhost:9080" -ForegroundColor White
    Write-Host "  • Web Service:  http://localhost:9082" -ForegroundColor White
} else {
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║       PROMOTION COMPLETE - SOME SERVICES NEED ATTENTION       ║" -ForegroundColor Yellow
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Check container logs for issues:" -ForegroundColor Yellow
    Write-Host "  docker-compose -f docker/docker-compose.prod.yml logs" -ForegroundColor DarkGray
}
Write-Host ""
