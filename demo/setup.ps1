<#
    CardioSaarthi -- one-command demo setup for a fresh laptop.

    Run from anywhere:   powershell -ExecutionPolicy Bypass -File demo\setup.ps1

    What it does, in the order the stack requires:
      1. checks Docker, a JDK and Node are installed
      2. writes .env from demo\env.demo if there is not one already
      3. starts PostgreSQL and waits for it to actually accept connections
      4. restores the case bank from artifacts\handover\cardiosaarthi-db.sql,
         but only into an empty database -- it never overwrites existing data
      5. installs the frontend's packages if they are missing

    It deliberately does not start the two servers. Those belong in their own
    windows so their logs are visible, and the script prints the two commands
    at the end.

    Written for Windows PowerShell 5.1, which has no && and no ternary.
#>

$ErrorActionPreference = 'Stop'

$repo      = Split-Path -Parent $PSScriptRoot
$dump      = Join-Path $repo 'artifacts\handover\cardiosaarthi-db.sql'
$container = 'cardiosaarthi-postgres'
# Must match demo\env.demo. Read from there rather than guessed, if .env exists.
$dbUser    = 'cardiosaarthi'
$dbName    = 'cardiosaarthi'

function Say([string]$text)  { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Good([string]$text) { Write-Host "    $text" -ForegroundColor Green }
function Warn([string]$text) { Write-Host "    $text" -ForegroundColor Yellow }
function Die([string]$text)  { Write-Host ""; Write-Host "!!! $text" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# 1. Prerequisites
# ---------------------------------------------------------------------------
Say 'Checking what is installed'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Die 'Docker was not found. Install Docker Desktop, start it, and run this again.'
}
& cmd /c 'docker info >nul 2>&1'
if ($LASTEXITCODE -ne 0) {
    Die 'Docker is installed but not running. Open Docker Desktop, wait for it to say Running, then run this again.'
}
Good 'Docker is running'

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    Die 'No JDK found. Install JDK 21 or newer (Temurin or Oracle), reopen the terminal, and run this again.'
}
$javaLine = (& cmd /c 'java -version 2>&1' | Select-Object -First 1)
$major = 0
if ($javaLine -match 'version "(\d+)') { $major = [int]$Matches[1] }
if ($major -lt 21) { Die "JDK 21 or newer is required. Found: $javaLine" }
Good "Java $major"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Die 'Node.js was not found. Install Node 20 or newer, reopen the terminal, and run this again.'
}
Good "Node $(& node -v)"

# The rendered ECGs are not in git -- they are 461 MB of PNG. Without them the
# app runs and every ECG is a broken image, which is worth catching here rather
# than on stage.
# The 479 MB of rendered ECGs are a release asset rather than a git object: a
# clone stays small, and a replaced asset does not mean a rewritten history.
# Downloaded once, then left alone.
$images = Join-Path $repo 'artifacts\images'
if (-not (Test-Path $images)) {
    $zip = Join-Path $repo 'artifacts\ecg-images.zip'
    New-Item -ItemType Directory -Force (Join-Path $repo 'artifacts') | Out-Null

    if (-not (Test-Path $zip)) {
        Write-Host '    downloading the rendered ECGs (479 MB, once)'
        $url = 'https://github.com/ThatGUY12034/CardioSaarthi/releases/download/demo-assets-v1/ecg-images.zip'
        # Invoke-WebRequest in PowerShell 5.1 buffers the whole body in memory and
        # its progress bar costs more than the download. curl ships with Windows.
        & curl.exe -L --fail --progress-bar -o $zip $url
        if ($LASTEXITCODE -ne 0) {
            Remove-Item $zip -ErrorAction SilentlyContinue
            Die "the download failed. Check the connection, or fetch it by hand from`n    $url`n    and save it as artifacts\ecg-images.zip, then run this again."
        }
    } else {
        Good 'found artifacts\ecg-images.zip already downloaded'
    }

    # A truncated download extracts without complaint and produces ECGs with the
    # bottom half missing, which is worse than a failure.
    $expected = (Get-Content (Join-Path $repo 'demo\ecg-images.zip.sha256') -Raw).Split()[0].Trim()
    $actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $expected.ToLower()) {
        Remove-Item $zip -ErrorAction SilentlyContinue
        Die 'the download is incomplete or corrupt and has been deleted. Run this again.'
    }
    Good 'checksum matches'

    Write-Host '    extracting'
    # tar ships with Windows 10 and later and reads a zip far faster than
    # Expand-Archive, which unpacks 1428 files one COM call at a time.
    Push-Location $repo
    try { & tar.exe -xf $zip }
    finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { Die 'extraction failed.' }
    Good 'rendered ECGs in place'
}
$pngCount = (Get-ChildItem $images -Filter *.png -ErrorAction SilentlyContinue | Measure-Object).Count
if ($pngCount -lt 100) { Warn "only $pngCount images found in artifacts\images; expected about 1428" }
else { Good "$pngCount rendered ECG images" }

# ---------------------------------------------------------------------------
# 2. Configuration
# ---------------------------------------------------------------------------
Say 'Configuration'

$envFile = Join-Path $repo '.env'
if (Test-Path $envFile) {
    Good '.env already exists, leaving it alone'
} else {
    Copy-Item (Join-Path $repo 'demo\env.demo') $envFile
    Good 'wrote .env from demo\env.demo'
}

$frontEnv = Join-Path $repo 'frontend\.env.local'
if (-not (Test-Path $frontEnv)) {
    Copy-Item (Join-Path $repo 'frontend\.env.example') $frontEnv
    Good 'wrote frontend\.env.local'
}

# ---------------------------------------------------------------------------
# 3. Database
# ---------------------------------------------------------------------------
Say 'Starting PostgreSQL'

Push-Location $repo
try { docker compose up -d }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { Die 'docker compose failed. The output above says why.' }

Write-Host '    waiting for the database to accept connections' -NoNewline
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    & cmd /c "docker exec $container pg_isready -U $dbUser -d $dbName >nul 2>&1"
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Write-Host '.' -NoNewline
    Start-Sleep -Seconds 2
}
Write-Host ''
if (-not $ready) { Die "the database did not become ready. Check: docker logs $container" }
Good 'database is up'

# ---------------------------------------------------------------------------
# 4. Case bank
# ---------------------------------------------------------------------------
Say 'Case bank'

# An error here means the table does not exist yet, which is the empty case.
$existing = & cmd /c "docker exec $container psql -U $dbUser -d $dbName -t -A -c ""select count(*) from cases"" 2>nul"
$rows = 0
if ($existing -match '^\d+$') { $rows = [int]$existing }

if ($rows -gt 0) {
    Good "$rows cases already loaded, nothing to restore"
} elseif (-not (Test-Path $dump)) {
    Warn 'no database dump found at artifacts\handover\cardiosaarthi-db.sql'
    Warn 'the app will start with an empty case bank; copy the dump across to get the 714 cases'
} else {
    Write-Host '    restoring 714 cases, this takes under a minute'
    # Redirected by cmd rather than piped from PowerShell: a 12 MB pipe through
    # PowerShell is re-encoded on the way, and psql then rejects it.
    & cmd /c "docker exec -i $container psql -U $dbUser -d $dbName -v ON_ERROR_STOP=1 -q < ""$dump"""
    if ($LASTEXITCODE -ne 0) { Die 'the restore failed. The output above says why.' }
    $loaded = & cmd /c "docker exec $container psql -U $dbUser -d $dbName -t -A -c ""select count(*) from cases"" 2>nul"
    Good "$loaded cases restored"
}

# ---------------------------------------------------------------------------
# 5. Frontend packages
# ---------------------------------------------------------------------------
Say 'Frontend packages'

if (Test-Path (Join-Path $repo 'frontend\node_modules')) {
    Good 'already installed'
} else {
    Push-Location (Join-Path $repo 'frontend')
    try { & npm install }
    finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { Die 'npm install failed. The output above says why.' }
    Good 'installed'
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ''
Write-Host 'Setup finished. Now open two terminals and run one command in each.' -ForegroundColor Green
Write-Host ''
Write-Host '  Terminal 1 -- the backend (wait for "Started ReviewApiApplication")'
Write-Host '    cd review-api; .\mvnw spring-boot:run' -ForegroundColor White
Write-Host ''
Write-Host '  Terminal 2 -- the interface'
Write-Host '    cd frontend; npm run dev' -ForegroundColor White
Write-Host ''
Write-Host '  Then open http://localhost:5173'
Write-Host '    faculty   TE/1234   password 1234'
Write-Host '    student   TE/4321   password 1234'
Write-Host ''
