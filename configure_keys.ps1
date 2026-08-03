$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$examplePath = Join-Path $projectRoot "backend\.env.example"
$envPath = Join-Path $projectRoot "backend\.env"

if (-not (Test-Path -LiteralPath $examplePath)) {
    throw "Missing configuration template: $examplePath"
}

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $examplePath -Destination $envPath
    Write-Host "Created private configuration file: backend/.env" -ForegroundColor Green
} else {
    Write-Host "Using existing private configuration file: backend/.env" -ForegroundColor Yellow
}

Write-Host "Enter only your own API keys and passwords. This file is excluded from Git." -ForegroundColor Cyan
Start-Process -FilePath "notepad.exe" -ArgumentList @($envPath)
