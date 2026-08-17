$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot "runtime\python312\python.exe"
Set-Location $ProjectRoot

if (-not (Test-Path $Python)) {
    Write-Host "Yisheng is not installed yet. Double-click setup.cmd first." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

& $Python -m app.desktop
