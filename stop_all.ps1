$ErrorActionPreference = "SilentlyContinue"

$runDir = Join-Path $PSScriptRoot ".run"
$pidFiles = @(
    (Join-Path $runDir "backend.pid"),
    (Join-Path $runDir "frontend.pid")
)

foreach ($pidFile in $pidFiles) {
    if (-not (Test-Path -LiteralPath $pidFile)) { continue }
    $savedPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    if ($savedPid -match "^\d+$") {
        $process = Get-Process -Id ([int]$savedPid)
        if ($process -and $process.ProcessName -match "^(python|py)(w)?$") {
            Stop-Process -Id ([int]$savedPid) -Force
        }
    }
    Remove-Item -LiteralPath $pidFile -Force
}

Write-Host "AutoLogic backend and frontend have stopped." -ForegroundColor Green
Start-Sleep -Seconds 1
