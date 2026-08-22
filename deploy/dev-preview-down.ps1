# Stops what dev-preview-up.ps1 started. The Postgres container is stopped, not removed, so its
# data survives -- dev-preview-up.ps1 will just docker start it again next time.
$ErrorActionPreference = "Continue"

$PgContainer = "knowledge-dev-preview"
$PidFile = Join-Path $env:TEMP "workspace-preview.pid"

Write-Host "==> backend"
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

Write-Host "==> Postgres ($PgContainer)"
docker inspect $PgContainer *> $null
if ($LASTEXITCODE -eq 0) {
    docker stop $PgContainer | Out-Null
    Write-Host "stopped (data preserved -- container not removed)"
} else {
    Write-Host "container not found"
}
