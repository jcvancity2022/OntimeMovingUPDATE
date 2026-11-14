@echo off
REM Runs the OnTime booking automation tests (see tests\e2e\README.md)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tests\e2e\run_tests.ps1"
