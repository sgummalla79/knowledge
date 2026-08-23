# Starts the local dev-preview stack: Postgres/pgvector via docker compose
# (deploy/docker-compose.dev-preview.yml), the Flask backend and the built frontend running
# natively (no app Docker image). Conventions mirror dev-preview-up.sh / CLAUDE.md's "Local dev
# preview" table — keep this in sync with dev-preview-down.ps1.
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepoRoot "deploy\docker-compose.dev-preview.yml"
$PgPort = 15432
$FlaskPort = 15100
$SecretKey = "dev-preview-secret"
$DatabaseUrl = "postgresql://rag:rag@127.0.0.1:$PgPort/rag"
$PidFile = Join-Path $env:TEMP "workspace-preview.pid"
$LogFile = Join-Path $env:TEMP "knowledge-dev-preview-flask.log"
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

Write-Host "==> building frontend"
Push-Location $Webui
npm run build
Pop-Location

Write-Host "==> backend"
$alreadyRunning = $false
if (Test-Path $PidFile) {
    $existingPid = Get-Content $PidFile
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        $alreadyRunning = $true
        Write-Host "already running (pid $existingPid)"
    }
}

if (-not $alreadyRunning) {
    $proc = Start-Process -FilePath $VenvPy `
        -ArgumentList @("-m", "flask", "--app", "api.wsgi", "run", "--port", "$FlaskPort") `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err" `
        -PassThru -WindowStyle Hidden
    $proc.Id | Out-File -FilePath $PidFile -Encoding ascii
    Start-Sleep -Seconds 1
    Write-Host "started (pid $($proc.Id)), logging to $LogFile"
}

Write-Host ""
Write-Host "Ready: http://127.0.0.1:$FlaskPort/sign-in"
