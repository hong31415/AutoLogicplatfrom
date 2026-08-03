$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$runDir = Join-Path $root ".run"
$backendPort = 8787
$frontendPort = 8790

New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$backendPidFile = Join-Path $runDir "backend.pid"
$frontendPidFile = Join-Path $runDir "frontend.pid"
$backendOutLog = Join-Path $runDir "backend.out.log"
$backendErrLog = Join-Path $runDir "backend.err.log"
$frontendOutLog = Join-Path $runDir "frontend.out.log"
$frontendErrLog = Join-Path $runDir "frontend.err.log"

function Stop-RecordedProcess([string]$pidFile) {
    if (-not (Test-Path -LiteralPath $pidFile)) { return }
    $savedPid = (Get-Content -LiteralPath $pidFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ($savedPid -match "^\d+$") {
        $process = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -match "^(python|py)(w)?$") {
            Stop-Process -Id ([int]$savedPid) -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 300
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

function Assert-PortFree([int]$port) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        throw "Port $port is already in use by process $($listener.OwningProcess). Run 关闭网站.bat first, then retry."
    }
}

# Some Windows launch environments expose both PATH and Path. Start-Process
# treats them as duplicate dictionary keys, so normalize them for this launcher.
$processEnvironment = [Environment]::GetEnvironmentVariables("Process")
$pathValue = $processEnvironment["Path"]
if (-not $pathValue) { $pathValue = $processEnvironment["PATH"] }
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")

$pythonCommand = Get-Command python -ErrorAction Stop
$python = $pythonCommand.Source

Stop-RecordedProcess $backendPidFile
Stop-RecordedProcess $frontendPidFile
Assert-PortFree $backendPort
Assert-PortFree $frontendPort

Write-Host "Starting AutoLogic backend and frontend..." -ForegroundColor Cyan
$backend = $null
$frontend = $null

try {
    $backend = Start-Process -FilePath $python -ArgumentList @("run.py") `
        -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $backendOutLog -RedirectStandardError $backendErrLog

    $frontend = Start-Process -FilePath $python -ArgumentList @("server.py") `
        -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $frontendOutLog -RedirectStandardError $frontendErrLog

    Set-Content -LiteralPath $backendPidFile -Value $backend.Id -Encoding ASCII
    Set-Content -LiteralPath $frontendPidFile -Value $frontend.Id -Encoding ASCII

    $ready = $false
    for ($attempt = 0; $attempt -lt 120; $attempt += 1) {
        Start-Sleep -Milliseconds 500
        if ($backend.HasExited) {
            $detail = Get-Content -LiteralPath $backendErrLog -Raw -ErrorAction SilentlyContinue
            throw "Backend startup failed. $detail"
        }
        if ($frontend.HasExited) {
            $detail = Get-Content -LiteralPath $frontendErrLog -Raw -ErrorAction SilentlyContinue
            throw "Frontend startup failed. $detail"
        }
        try {
            $backendHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/api/v1/health" -TimeoutSec 2
            $proxyHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$frontendPort/api/v1/health" -TimeoutSec 2
            if ($backendHealth.ok -and $proxyHealth.ok) {
                $ready = $true
                break
            }
        } catch {
            # Backend initialization can take several seconds.
        }
    }

    if (-not $ready) {
        throw "Startup timed out. Check the log files in $runDir."
    }
} catch {
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
    if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $backendPidFile, $frontendPidFile -Force -ErrorAction SilentlyContinue
    throw
}

$url = "http://127.0.0.1:$frontendPort/"
if ($env:AUTOLOGIC_SKIP_BROWSER -notin @("1", "true", "yes")) {
    Start-Process $url
}

Write-Host ""
Write-Host "AutoLogic Studio is running." -ForegroundColor Green
Write-Host "Website: $url"
Write-Host "Backend: http://127.0.0.1:$backendPort/api/v1/health"
Write-Host "Frontend API proxy: connected"
Write-Host "Use 关闭网站.bat to stop both services."
