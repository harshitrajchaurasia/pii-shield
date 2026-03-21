<#
.SYNOPSIS
    Deploy PI Remover to DEVELOPMENT environment (Microservices Architecture).

.DESCRIPTION
    Builds and deploys the PI Remover services to the development environment.
    Uses YAML configuration files instead of environment variables.
    
    Architecture:
    - API Service (pi-gateway): Port 8080
    - Web Service (pi-web): Port 8082 -> calls API via HTTP
    - Redis: Port 6379 (internal)

.PARAMETER Build
    Force rebuild of Docker images.

.PARAMETER Detach
    Run containers in detached mode (default: true).

.PARAMETER Follow
    Follow logs after starting.

.PARAMETER ConfigPath
    Path to configuration directory (default: config/).

.EXAMPLE
    .\deploy-dev.ps1
    
.EXAMPLE
    .\deploy-dev.ps1 -Build -Follow

.EXAMPLE
    .\deploy-dev.ps1 -ConfigPath "C:\my-config"
#>

[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$Detach = $true,
    [switch]$Follow,
    [string]$ConfigPath
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DockerDir = Join-Path $ProjectRoot "docker"
$DevComposeFile = Join-Path $DockerDir "docker-compose.dev.yml"
$DefaultConfigDir = Join-Path $ProjectRoot "config"

# Use custom config path or default
if (-not $ConfigPath) {
    $ConfigPath = $DefaultConfigDir
}

# Banner
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      PI REMOVER - DEVELOPMENT DEPLOYMENT (Microservices)     ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "Architecture: API Service (8080) <- Web Service (8082)" -ForegroundColor Yellow
Write-Host ""

# Verify files exist
if (-not (Test-Path $DevComposeFile)) {
    Write-Error "Dev compose file not found: $DevComposeFile"
    exit 1
}

# Verify config directory
if (-not (Test-Path $ConfigPath)) {
    Write-Warning "Config directory not found: $ConfigPath"
    Write-Host "Creating default configuration..." -ForegroundColor Yellow
}

# Verify required config files
$requiredConfigs = @("api_service.yaml", "web_service.yaml", "clients.yaml")
foreach ($cfg in $requiredConfigs) {
    $cfgPath = Join-Path $ConfigPath $cfg
    if (-not (Test-Path $cfgPath)) {
        Write-Warning "Config file not found: $cfgPath"
    }
}

# Create logs directory if it doesn't exist
$LogsDir = Join-Path $ProjectRoot "logs\dev"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
    Write-Host "[INFO] Created logs directory: $LogsDir" -ForegroundColor Yellow
}

# Build compose command (standalone dev file)
$composeArgs = @("-f", $DevComposeFile)

# Run commands
try {
    Write-Host "[STEP 1/4] Stopping existing containers..." -ForegroundColor Green
    & docker-compose @composeArgs down --remove-orphans 2>$null

    Write-Host "[STEP 2/4] Building and starting services..." -ForegroundColor Green
    Write-Host "           Config path: $ConfigPath" -ForegroundColor DarkGray
    
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
        Write-Host "[STEP 3/4] Verifying deployment..." -ForegroundColor Green
        Start-Sleep -Seconds 5
        
        & docker-compose @composeArgs ps

        Write-Host ""
        Write-Host "[STEP 4/4] Checking service health..." -ForegroundColor Green
        
        # Check API service health
        try {
            $apiHealth = Invoke-RestMethod -Uri "http://localhost:8080/docs" -TimeoutSec 10
            Write-Host "  API Service (8080): " -NoNewline
            Write-Host "HEALTHY" -ForegroundColor Green
        } catch {
            Write-Host "  API Service (8080): " -NoNewline
            Write-Host "STARTING..." -ForegroundColor Yellow
        }
        
        # Check Web service health
        try {
            $webHealth = Invoke-RestMethod -Uri "http://localhost:8082/health" -TimeoutSec 10
            Write-Host "  Web Service (8082): " -NoNewline
            Write-Host "HEALTHY" -ForegroundColor Green
        } catch {
            Write-Host "  Web Service (8082): " -NoNewline
            Write-Host "STARTING..." -ForegroundColor Yellow
        }

        Write-Host ""
        Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
        Write-Host "║                  DEVELOPMENT DEPLOYMENT COMPLETE              ║" -ForegroundColor Green
        Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
        Write-Host ""
        Write-Host "Services available at:" -ForegroundColor Cyan
        Write-Host "  • API Gateway:  http://localhost:8080" -ForegroundColor White
        Write-Host "  • API Docs:     http://localhost:8080/docs" -ForegroundColor White
        Write-Host "  • Web Service:  http://localhost:8082" -ForegroundColor White
        Write-Host ""
        Write-Host "DEV Credentials (from config/clients.yaml):" -ForegroundColor Cyan
        Write-Host "  • Client ID:     pi-dev-client" -ForegroundColor White
        Write-Host "  • Client Secret: YOUR_DEV_CLIENT_SECRET_HERE" -ForegroundColor White
        Write-Host ""
        Write-Host "API Endpoints:" -ForegroundColor Cyan
        Write-Host "  • Auth:    POST http://localhost:8080/dev/auth/token" -ForegroundColor DarkGray
        Write-Host "  • Redact:  POST http://localhost:8080/dev/v1/redact" -ForegroundColor DarkGray
        Write-Host "  • Health:  GET  http://localhost:8080/dev/health" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "Useful commands:" -ForegroundColor Cyan
        Write-Host "  • View logs:  docker-compose -f docker/docker-compose.dev.yml logs -f" -ForegroundColor DarkGray
        Write-Host "  • Stop:       docker-compose -f docker/docker-compose.dev.yml down" -ForegroundColor DarkGray
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
    Write-Host "║                     DEPLOYMENT FAILED                         ║" -ForegroundColor Red
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host ""
    Write-Error $_.Exception.Message
    exit 1
}
