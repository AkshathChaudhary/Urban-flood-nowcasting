# FLOWS Urban Flood Nowcasting PowerShell Dev Launcher
Set-Location $PSScriptRoot
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  FLOWS Urban Flood Nowcasting - Dev Launcher (PowerShell)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" run_dev.py @args
} else {
    & python run_dev.py @args
}
