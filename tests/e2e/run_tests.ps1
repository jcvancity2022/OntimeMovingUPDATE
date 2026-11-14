# OnTime Moving — run the booking automation tests on Windows.
# Double-click run_booking_tests.bat in the project folder, or run:
#   powershell -ExecutionPolicy Bypass -File tests\e2e\run_tests.ps1
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $here '.venv'

Write-Host "`n=== OnTime Moving - booking automation tests ===`n" -ForegroundColor Cyan

if (-not (Test-Path $venv)) {
    Write-Host 'First run: setting up (about a minute)...' -ForegroundColor Yellow
    python -m venv $venv
    & "$venv\Scripts\python.exe" -m pip install -q --upgrade pip
    & "$venv\Scripts\python.exe" -m pip install -q -r (Join-Path $here 'requirements.txt')
    & "$venv\Scripts\python.exe" -m playwright install chromium
}

if (-not $env:ONTIME_STAFF_EMAIL)    { $env:ONTIME_STAFF_EMAIL = Read-Host 'Staff email' }
if (-not $env:ONTIME_STAFF_PASSWORD) {
    $secure = Read-Host 'Staff password' -AsSecureString
    $env:ONTIME_STAFF_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}

$show = Read-Host 'Watch the browser while it tests? (y/N)'
if ($show -match '^[yY]') { $env:ONTIME_HEADED = '1' }

Push-Location $here
try { & "$venv\Scripts\python.exe" -m pytest; $code = $LASTEXITCODE } finally { Pop-Location }

if ($code -eq 0) { Write-Host "`nAll booking tests passed." -ForegroundColor Green }
else { Write-Host "`nSome tests failed - screenshots are in tests\e2e\artifacts" -ForegroundColor Red }
$env:ONTIME_STAFF_PASSWORD = $null
Read-Host 'Press Enter to close'
exit $code
