# Everything needed to put CardioSaarthi on a public link, in one command.
#
# Brings the containerised stack up, waits until the API actually answers
# through it rather than just until the containers exist, opens a Cloudflare
# quick tunnel, and prints the public address with a QR code beside it.
#
# Run it, read the address off the screen, and leave the window open. Closing
# it takes the link down.
#
#   .\demo\present.ps1
#
# There is no account, no card and no configuration: a quick tunnel is
# anonymous and temporary. The address is different every run, so start this
# before the room fills up rather than during.

param(
    # Bring the stack up and check it answers, without publishing anything.
    # Worth running once before the day itself: it proves the containers and
    # the data are fine while nothing is reachable from outside this machine.
    [switch] $NoTunnel
)

$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$local = 'http://localhost:5173'
$logFile = Join-Path $env:TEMP 'cardiosaarthi-tunnel.log'
$linkFile = Join-Path $repo 'demo\LIVE-LINK.txt'
$qrFile = Join-Path $repo 'demo\LIVE-LINK-qr.png'

function Say([string] $text, [string] $colour = 'Gray') {
    Write-Host $text -ForegroundColor $colour
}

# ---------------------------------------------------------------- the binary
# winget puts cloudflared on PATH, but only for shells opened after the
# install, so the known location is worth checking before giving up on it.
$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) {
    $fallback = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
    if (Test-Path $fallback) { $cloudflared = $fallback }
}
if (-not $cloudflared) {
    Say 'cloudflared is not installed. Install it with:' 'Red'
    Say '    winget install --id Cloudflare.cloudflared' 'Yellow'
    exit 1
}

# ----------------------------------------------------------------- the stack
Say ''
Say '  CardioSaarthi - going live' 'Cyan'
Say '  =========================' 'Cyan'
Say ''

# Every redirection below happens inside cmd, never in PowerShell. Windows
# PowerShell 5.1 wraps a native command's stderr in error records, and with
# $ErrorActionPreference = 'Stop' that kills the script on output the command
# considers perfectly normal -- docker compose writes its progress to stderr
# even when everything worked.
cmd /c "docker info >nul 2>&1"
if ($LASTEXITCODE -ne 0) {
    Say '  Docker is not running. Start Docker Desktop, wait for the whale icon' 'Red'
    Say '  to stop animating, then run this again.' 'Red'
    exit 1
}
Say '  [1/4] Docker is running.' 'Green'

Push-Location $repo
try {
    cmd /c "docker compose --profile demo up -d >nul 2>&1"
    if ($LASTEXITCODE -ne 0) {
        Say '  The stack did not start. Run this to see why:' 'Red'
        Say '      docker compose --profile demo up' 'Yellow'
        exit 1
    }
} finally {
    Pop-Location
}
Say '  [2/4] Containers started.' 'Green'

# Containers being up is not the same as the application answering: the API
# spends the better part of a minute on Flyway and the Spring context, and a
# link handed out before then shows a broken page to whoever opens it first.
Say '        Waiting for the API (this takes up to a minute)...'
$ready = $false
foreach ($attempt in 1..90) {
    try {
        $probe = Invoke-WebRequest -Uri "$local/api/auth/login/faculty" -Method Post `
            -ContentType 'application/json' -Body '{}' -TimeoutSec 3 `
            -UseBasicParsing -ErrorAction Stop
        $ready = $true
    } catch {
        # 400 and 401 both mean the API is listening and reading the request,
        # which is what is being tested here. Only a refused connection or a
        # gateway error means it is not up yet.
        $status = $_.Exception.Response.StatusCode.value__
        if ($status -eq 400 -or $status -eq 401) { $ready = $true }
    }
    if ($ready) { break }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Say '  The API never came up. Check its log with:' 'Red'
    Say '      docker compose logs review-api --tail 40' 'Yellow'
    exit 1
}
Say '  [3/4] The application answers on http://localhost:5173' 'Green'

if ($NoTunnel) {
    Say ''
    Say '  Checked, and nothing published: -NoTunnel was given.' 'Cyan'
    Say "  The stack is running on $local"
    Say ''
    Say '  Run it again without -NoTunnel to get a public link.' 'Yellow'
    Say ''
    exit 0
}

# ---------------------------------------------------------------- the tunnel
# --logfile rather than reading the console: PowerShell 5.1 wraps a native
# command's stderr in error records, and cloudflared writes its banner there.
if (Test-Path $logFile) { Remove-Item $logFile -Force }

$tunnel = Start-Process -FilePath $cloudflared -PassThru -WindowStyle Hidden `
    -ArgumentList @('tunnel', '--url', $local, '--logfile', $logFile)

$url = $null
foreach ($attempt in 1..60) {
    Start-Sleep -Seconds 1
    if (Test-Path $logFile) {
        $match = Select-String -Path $logFile -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' `
            -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($match) {
            $url = $match.Matches[0].Value
            break
        }
    }
    if ($tunnel.HasExited) { break }
}

if (-not $url) {
    Say '  The tunnel did not come up. Its log is at:' 'Red'
    Say "      $logFile" 'Yellow'
    if (-not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force }
    exit 1
}

Set-Content -Path $linkFile -Value $url -Encoding utf8
Say '  [4/4] Public link is live.' 'Green'

# A QR code so the panel can open it on a phone without typing a random
# three-word address. Written as an image rather than drawn in the console:
# the block characters a terminal QR needs are not in the default Windows
# code page, and a picture can go on the projector anyway.
try {
    $qrScript = @"
import qrcode, sys
qrcode.make(sys.argv[1]).resize((600, 600)).save(sys.argv[2])
"@
    $qrScript | Out-File -FilePath "$env:TEMP\cs_qr.py" -Encoding utf8
    cmd /c "python ""$env:TEMP\cs_qr.py"" ""$url"" ""$qrFile"" >nul 2>&1"
} catch {
    Say '  (no QR code - python or the qrcode package is missing, link still works)' 'DarkGray'
}

Say ''
Say '  ============================================================' 'Cyan'
Say ''
Say "     $url" 'White'
Say ''
Say '  ============================================================' 'Cyan'
Say ''
Say "  Saved to : $linkFile"
if (Test-Path $qrFile) { Say "  QR code  : $qrFile" }
Say ''
Say '  Demonstration logins   Faculty  TE/1234    password 1234'
Say '                         Student  TE/4321    password 1234'
Say '                         Patient  PT/1234    password 1234'
Say '                         Admin    /login/admin, Email Login tab'
Say ''
# The enrolled students' college IDs are safe to print; their password is not.
# This file is committed to a public repository, and one password covers all
# three accounts, so it belongs with the presenter rather than in the open.
Say '  Enrolled students      TE23CS001  TE23CS015  TE23CS022' 'DarkGray'
Say '                         (password not printed here - see your own notes)' 'DarkGray'
Say ''
Say '  Leave this window open. Press Ctrl-C to take the link down.' 'Yellow'
Say ''
# The tunnel runs as a hidden child process, so closing this window with the X
# instead of pressing Ctrl-C would orphan it: the window disappears, the link
# stays up, and nobody is watching it. Worth knowing how to kill it by hand.
Say "  If you close this window by accident, the link stays up. Stop it with:" 'DarkGray'
Say "      Stop-Process -Id $($tunnel.Id)" 'DarkGray'
Say ''

try {
    Wait-Process -Id $tunnel.Id
} finally {
    if (-not $tunnel.HasExited) {
        Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue
    }
    Say ''
    Say '  Link closed. The stack is still running on http://localhost:5173' 'Gray'
    Say '  Stop it with:  docker compose --profile demo down' 'Gray'
}
