# Stops what dev-preview-up.ps1 started. The Postgres container is stopped, not removed, so its
# data survives -- dev-preview-up.ps1 will just `docker compose up -d` it again next time.
$ErrorActionPreference = "Continue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepoRoot "deploy\docker-compose.dev-preview.yml"
$FlaskPidFile = Join-Path $env:TEMP "workspace-preview.pid"
$VitePidFile = Join-Path $env:TEMP "workspace-preview-vite.pid"

function Stop-PidFile($Label, $PidFile) {
    Write-Host "==> $Label"
    if (Test-Path $PidFile) {
        $existingPid = Get-Content $PidFile
        $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $existingPid -Force
            Write-Host "stopped (pid $existingPid)"
        } else {
            Write-Host "no process at pid $existingPid (already stopped)"
        }
        Remove-Item $PidFile -ErrorAction SilentlyContinue
    } else {
        Write-Host "no PID file, nothing to stop"
    }
}

Stop-PidFile "backend" $FlaskPidFile
Stop-PidFile "frontend (Vite dev server)" $VitePidFile

Write-Host "==> Postgres (knowledge-dev-preview)"
docker compose -p knowledge-dev-preview -f $ComposeFile stop
