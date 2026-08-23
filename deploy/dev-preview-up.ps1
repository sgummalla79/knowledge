# Starts the local dev-preview stack: Postgres/pgvector via docker compose
# (deploy/docker-compose.dev-preview.yml), the Flask backend, and webui/'s own Vite dev server --
# three separate processes/containers, matching this repo's standalone-API architecture (see
# CLAUDE.md session history item 34: this API renders no HTML/SPA of any kind, so webui/ must run
# on its own, not built-and-served-by-Flask as it used to be). Conventions mirror dev-preview-up.sh
# / CLAUDE.md's "Local dev preview" table -- keep this in sync with dev-preview-down.ps1.
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepoRoot "deploy\docker-compose.dev-preview.yml"
$PgPort = 15432
$FlaskPort = 15100
$VitePort = 5173
$SecretKey = "dev-preview-secret"
$DatabaseUrl = "postgresql://rag:rag@127.0.0.1:$PgPort/rag"
$FlaskPidFile = Join-Path $env:TEMP "workspace-preview.pid"
$FlaskLogFile = Join-Path $env:TEMP "knowledge-dev-preview-flask.log"
$VitePidFile = Join-Path $env:TEMP "workspace-preview-vite.pid"
$ViteLogFile = Join-Path $env:TEMP "knowledge-dev-preview-vite.log"
$VenvPy = Join-Path $RepoRoot "api\.venv\Scripts\python.exe"

Write-Host "==> Postgres (knowledge-dev-preview)"
docker compose -p knowledge-dev-preview -f $ComposeFile up -d

Write-Host "==> waiting for Postgres to accept connections"
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    docker compose -p knowledge-dev-preview -f $ComposeFile exec -T knowledge-dev-preview pg_isready -U rag *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    Write-Error "Postgres did not become ready in time"
    exit 1
}

if (-not (Test-Path $VenvPy)) {
    Write-Host "==> creating api/.venv"
    python -m venv (Join-Path $RepoRoot "api\.venv")
    & $VenvPy -m pip install -q -r (Join-Path $RepoRoot "api\requirements.txt") -r (Join-Path $RepoRoot "api\requirements-dev.txt")
}

Write-Host "==> running migrations"
$env:DATABASE_URL = $DatabaseUrl
$env:SECRET_KEY = $SecretKey
& $VenvPy -m alembic -c (Join-Path $RepoRoot "api\alembic.ini") upgrade head

$Webui = Join-Path $RepoRoot "webui"
if (-not (Test-Path (Join-Path $Webui "node_modules"))) {
    Write-Host "==> installing frontend dependencies"
    Push-Location $Webui
    npm install
    Pop-Location
}

Write-Host "==> backend"
$flaskAlreadyRunning = $false
if (Test-Path $FlaskPidFile) {
    $existingPid = Get-Content $FlaskPidFile
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        $flaskAlreadyRunning = $true
        Write-Host "already running (pid $existingPid)"
    }
}

if (-not $flaskAlreadyRunning) {
    $proc = Start-Process -FilePath $VenvPy `
        -ArgumentList @("-m", "flask", "--app", "api.wsgi", "run", "--port", "$FlaskPort") `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $FlaskLogFile -RedirectStandardError "$FlaskLogFile.err" `
        -PassThru -WindowStyle Hidden
    $proc.Id | Out-File -FilePath $FlaskPidFile -Encoding ascii
    Start-Sleep -Seconds 1
    Write-Host "started (pid $($proc.Id)), logging to $FlaskLogFile"
}

Write-Host "==> frontend (Vite dev server)"
$viteAlreadyRunning = $false
if (Test-Path $VitePidFile) {
    $existingPid = Get-Content $VitePidFile
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        $viteAlreadyRunning = $true
        Write-Host "already running (pid $existingPid)"
    }
}

if (-not $viteAlreadyRunning) {
    # VITE_API_BASE_URL overrides webui/.env.development's own default (which points at the
    # verify/"prod" API port, 13102 -- see CLAUDE.md session history item 35) to this Flask instance.
    $env:VITE_API_BASE_URL = "http://127.0.0.1:$FlaskPort"
    $proc = Start-Process -FilePath "npm" `
        -ArgumentList @("run", "dev") `
        -WorkingDirectory $Webui `
        -RedirectStandardOutput $ViteLogFile -RedirectStandardError "$ViteLogFile.err" `
        -PassThru -WindowStyle Hidden
    $proc.Id | Out-File -FilePath $VitePidFile -Encoding ascii
    Start-Sleep -Seconds 1
    Write-Host "started (pid $($proc.Id)), logging to $ViteLogFile"
}

Write-Host ""
Write-Host "Ready: http://127.0.0.1:$VitePort/sign-in"
