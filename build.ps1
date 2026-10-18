$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

py -3 -m PyInstaller --noconfirm --clean --onefile --noconsole `
  --name BatteryTray --icon assets\battery.ico `
  --add-data "assets\battery.ico;assets" `
  --version-file version_info.txt main.py

& .\tools\strip-motw.ps1 -Path '.\dist'
& .\tools\strip-motw.ps1 -Path '.\dist' -Verify
