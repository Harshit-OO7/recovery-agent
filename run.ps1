param (
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("install", "dev", "seed", "run-batch", "test")]
    [string]$Command
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BackendDir = Join-Path $PSScriptRoot "backend"

switch ($Command) {
    "install" {
        Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
        Push-Location $BackendDir
        python -m pip install -r requirements.txt
        Pop-Location
    }
    "dev" {
        Write-Host "Starting FastAPI dev server on http://localhost:8000..." -ForegroundColor Green
        Push-Location $BackendDir
        python -m uvicorn app.main:app --reload --port 8000
        Pop-Location
    }
    "test" {
        Write-Host "Running backend tests with pytest..." -ForegroundColor Yellow
        Push-Location $BackendDir
        python -m pytest -v tests/
        Pop-Location
    }
    "seed" {
        Write-Host "Generating synthetic dataset..." -ForegroundColor Cyan
        Push-Location $BackendDir
        python -m app.data.seed
        Pop-Location
    }
    "run-batch" {
        Write-Host "Running orchestrator batch recovery run..." -ForegroundColor Cyan
        Push-Location $BackendDir
        python -m app.orchestrator.runner
        Pop-Location
    }
}
