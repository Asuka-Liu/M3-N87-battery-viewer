$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

py -3 -m PyInstaller --noconfirm --clean --onefile --noconsole `
  --name BatteryTray --icon assets\battery.ico `
  --add-data "assets\battery.ico;assets" main.py

Write-Host "built: dist\BatteryTray.exe"
