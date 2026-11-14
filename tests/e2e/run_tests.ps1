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

# Supabase project + public key come from api-config.js (or the environment)
$cfg = Get-Content (Join-Path $here '..\..\api-config.js') -Raw
$sbUrl = if ($env:SUPABASE_URL) { $env:SUPABASE_URL } else { ([regex]"const SUPABASE_URL = '([^']*)'").Match($cfg).Groups[1].Value }
$sbKey = if ($env:SUPABASE_ANON_KEY) { $env:SUPABASE_ANON_KEY } else { ([regex]"const SUPABASE_ANON_KEY = '([^']*)'").Match($cfg).Groups[1].Value }

function Test-StaffLogin([string]$email, [string]$password) {
    try {
        $body = @{ email = $email; password = $password } | ConvertTo-Json
        Invoke-RestMethod -Method Post -Uri "$sbUrl/auth/v1/token?grant_type=password" `
            -Headers @{ apikey = $sbKey } -ContentType 'application/json' -Body $body | Out-Null
        return $true
    } catch { return $false }
}

# Ask for the staff login and check it right away (up to 3 tries)
for ($try = 1; $try -le 3; $try++) {
    if (-not $env:ONTIME_STAFF_EMAIL) { $env:ONTIME_STAFF_EMAIL = (Read-Host 'Staff email').Trim() }
    if (-not $env:ONTIME_STAFF_PASSWORD) {
        $secure = Read-Host 'Staff password' -AsSecureString
        $env:ONTIME_STAFF_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    }
    Write-Host 'Checking sign-in...' -NoNewline
    if (Test-StaffLogin $env:ONTIME_STAFF_EMAIL $env:ONTIME_STAFF_PASSWORD) { Write-Host ' OK' -ForegroundColor Green; break }
    Write-Host ' email or password not accepted - try again.' -ForegroundColor Red
    $env:ONTIME_STAFF_EMAIL = $null; $env:ONTIME_STAFF_PASSWORD = $null
    if ($try -eq 3) {
        Write-Host 'Tip: use the same login as the admin dashboard (login.html).' -ForegroundColor Yellow
        Read-Host 'Press Enter to close'; exit 2
    }
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
