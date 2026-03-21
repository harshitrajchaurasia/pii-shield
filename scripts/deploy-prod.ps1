<#
.SYNOPSIS
    Deploy PI Remover to PRODUCTION environment.

.DESCRIPTION
    Builds and deploys the PI Remover services to the production environment
    with strict security settings and minimal logging.

.PARAMETER Build
    Force rebuild of Docker images.

.PARAMETER Detach
    Run containers in detached mode (default: true).

.PARAMETER Follow
    Follow logs after starting.

.PARAMETER SkipConfirmation
    Skip the production deployment confirmation prompt.

.EXAMPLE
    .\deploy-prod.ps1
    
.EXAMPLE
    .\deploy-prod.ps1 -Build -SkipConfirmation
#>

[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$Detach = $true,
    [switch]$Follow,
    [switch]$SkipConfirmation
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DockerDir = Join-Path $ProjectRoot "docker"
$ComposeFile = Join-Path $DockerDir "docker-compose.prod.yml"
$EnvFile = Join-Path $DockerDir ".env.prod"
$EnvTemplate = Join-Path $DockerDir ".env.prod.template"

# Banner
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║           PI REMOVER - PRODUCTION DEPLOYMENT                  ║" -ForegroundColor Magenta
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

# Verify files exist
if (-not (Test-Path $ComposeFile)) {
    Write-Error "Docker compose file not found: $ComposeFile"
    exit 1
}

# Check for production environment file
if (-not (Test-Path $EnvFile)) {
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Red
    Write-Host "║                    MISSING CONFIGURATION                      ║" -ForegroundColor Red
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host ""
    Write-Host "Production environment file not found: $EnvFile" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To fix this:" -ForegroundColor Cyan
    Write-Host "  1. Copy the template:  cp docker\.env.prod.template docker\.env.prod" -ForegroundColor White
    Write-Host "  2. Edit .env.prod and set production secrets" -ForegroundColor White
    Write-Host "  3. Re-run this script" -ForegroundColor White
    Write-Host ""
    exit 1
}

# Production confirmation
if (-not $SkipConfirmation) {
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║                    ⚠️  PRODUCTION DEPLOYMENT                   ║" -ForegroundColor Yellow
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "You are about to deploy to PRODUCTION." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This will:" -ForegroundColor Cyan
    Write-Host "  • Stop existing production containers" -ForegroundColor White
    Write-Host "  • Build new images (if -Build specified)" -ForegroundColor White
    Write-Host "  • Start production services on ports 9080/9082" -ForegroundColor White
    Write-Host ""
    
    $confirmation = Read-Host "Type 'DEPLOY' to confirm production deployment"
    if ($confirmation -ne "DEPLOY") {
        Write-Host ""
        Write-Host "Deployment cancelled." -ForegroundColor Yellow
        exit 0
    }
    Write-Host ""
}

# Build arguments
$composeArgs = @("-f", $ComposeFile, "--env-file", $EnvFile)

# Run commands
try {
    Write-Host "[STEP 1/4] Validating configuration..." -ForegroundColor Green
    
    # Basic validation of env file
    $envContent = Get-Content $EnvFile -Raw
    if ($envContent -match "REPLACE_WITH") {
        Write-Host ""
        Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Red
        Write-Host "║                 UNCONFIGURED SECRETS DETECTED                 ║" -ForegroundColor Red
        Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Red
        Write-Host ""
        Write-Host "Your .env.prod file still contains template placeholders." -ForegroundColor Yellow
        Write-Host "Please update all 'REPLACE_WITH...' values with actual secrets." -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }

    Write-Host "[STEP 2/4] Stopping existing containers..." -ForegroundColor Green
    & docker-compose @composeArgs down --remove-orphans 2>$null

    Write-Host "[STEP 3/4] Building and starting services..." -ForegroundColor Green
    $upArgs = @("up")
    if ($Build) {
        $upArgs += "--build"
    }
    if ($Detach -and -not $Follow) {
        $upArgs += "-d"
    }
    
    & docker-compose @composeArgs @upArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed with exit code $LASTEXITCODE"
    }

    if ($Detach -and -not $Follow) {
        Write-Host ""
        Write-Host "[STEP 4/4] Verifying deployment..." -ForegroundColor Green
        Start-Sleep -Seconds 10  # Longer wait for production
        
        & docker-compose @composeArgs ps

        # Health check
        Write-Host ""
        Write-Host "[INFO] Running health checks..." -ForegroundColor Yellow
        $healthCheckPassed = $true
        
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:9080/prod/health" -TimeoutSec 10 -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                Write-Host "  • API Gateway: HEALTHY" -ForegroundColor Green
            }
        } catch {
            Write-Host "  • API Gateway: UNHEALTHY - $_" -ForegroundColor Red
            $healthCheckPassed = $false
        }
        
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:9082/health" -TimeoutSec 10 -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                Write-Host "  • Web Service: HEALTHY" -ForegroundColor Green
            }
        } catch {
            Write-Host "  • Web Service: UNHEALTHY - $_" -ForegroundColor Red
            $healthCheckPassed = $false
        }

        Write-Host ""
        if ($healthCheckPassed) {
            Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
            Write-Host "║               PRODUCTION DEPLOYMENT SUCCESSFUL                ║" -ForegroundColor Green
            Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
        } else {
            Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
            Write-Host "║      DEPLOYMENT COMPLETE - SOME HEALTH CHECKS FAILED         ║" -ForegroundColor Yellow
            Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
        }
        Write-Host ""
        Write-Host "Production services available at:" -ForegroundColor Cyan
        Write-Host "  • API Gateway:  http://localhost:9080" -ForegroundColor White
        Write-Host "  • Web Service:  http://localhost:9082" -ForegroundColor White
        Write-Host ""
        Write-Host "Useful commands:" -ForegroundColor Cyan
        Write-Host "  • View logs:  docker-compose -f docker/docker-compose.prod.yml logs -f" -ForegroundColor DarkGray
        Write-Host "  • Stop:       docker-compose -f docker/docker-compose.prod.yml down" -ForegroundColor DarkGray
        Write-Host ""
    }

    if ($Follow) {
        Write-Host ""
        Write-Host "[INFO] Following logs (Ctrl+C to stop)..." -ForegroundColor Yellow
        & docker-compose @composeArgs logs -f
    }

} catch {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Red
    Write-Host "║                PRODUCTION DEPLOYMENT FAILED                   ║" -ForegroundColor Red
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host ""
    Write-Error $_.Exception.Message
    exit 1
}
