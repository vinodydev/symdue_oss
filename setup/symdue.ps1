param(
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$SERVER_ENV = Join-Path $SCRIPT_DIR "..\server\.env"
$SERVER_ENV_EXAMPLE = Join-Path $SCRIPT_DIR "..\server\.env.example"

function Info($msg) {
    Write-Host "[INFO] $msg" -ForegroundColor Cyan
}

function Ok($msg) {
    Write-Host "[OK] $msg" -ForegroundColor Green
}

function Warn($msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

function Err($msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
}

function Section($msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor White
}

function Random-Password {

    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    -join (1..32 | ForEach-Object {
        $chars[(Get-Random -Minimum 0 -Maximum $chars.Length)]
    })
}

function Random-Secret {

    return [guid]::NewGuid().ToString("N") +
           [guid]::NewGuid().ToString("N")
}

function Cmd-Init {

    if (-not (Test-Path $SERVER_ENV_EXAMPLE)) {

        Err ".env.example not found"
        exit 1
    }

    Section "Generating .env"

    Copy-Item $SERVER_ENV_EXAMPLE $SERVER_ENV -Force

    $pgPassword = Random-Password
    $secretKey = Random-Secret

    $content = Get-Content $SERVER_ENV -Raw

    $content = $content.Replace(
        "<set-via-setup-or-environment>",
        $pgPassword
    )

    $content = $content.Replace(
        "<run: openssl rand -hex 32>",
        $secretKey
    )

    Set-Content $SERVER_ENV $content

    Ok ".env generated"

    Write-Host ""
    Write-Host "Next:"
    Write-Host ".\symdue.ps1 start"
}

function Cmd-Start {

    Section "Starting stack"

    Push-Location $SCRIPT_DIR

    try {

        docker compose `
            -f docker-compose.yml `
            -f docker-compose.windows.yml `
            up -d
    }
    finally {

        Pop-Location
    }

    Ok "Stack started"
}

function Cmd-Stop {

    Push-Location $SCRIPT_DIR

    try {

        docker compose `
            -f docker-compose.yml `
            -f docker-compose.windows.yml `
            stop
    }
    finally {

        Pop-Location
    }

    Ok "Stack stopped"
}

function Cmd-Logs {

    Push-Location $SCRIPT_DIR

    try {

        docker compose `
            -f docker-compose.yml `
            -f docker-compose.windows.yml `
            logs -f
    }
    finally {

        Pop-Location
    }
}

function Cmd-Status {

    Push-Location $SCRIPT_DIR

    try {

        docker compose `
            -f docker-compose.yml `
            -f docker-compose.windows.yml `
            ps
    }
    finally {

        Pop-Location
    }
}

switch ($Command) {

    "init" {
        Cmd-Init
    }

    "start" {
        Cmd-Start
    }

    "stop" {
        Cmd-Stop
    }

    "logs" {
        Cmd-Logs
    }

    "status" {
        Cmd-Status
    }

    default {

        Write-Host ""
        Write-Host "Usage:"
        Write-Host "  .\symdue.ps1 init"
        Write-Host "  .\symdue.ps1 start"
        Write-Host "  .\symdue.ps1 stop"
        Write-Host "  .\symdue.ps1 logs"
        Write-Host "  .\symdue.ps1 status"
    }
}