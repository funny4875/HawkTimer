$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name HawkTimer --icon assets/icon.ico --add-data 'assets/icon.ico;.' --add-data 'mihawk_idle.gif;.' --add-data 'mihawk_action.gif;.' --add-data 'mihawk_hat.gif;.' --collect-all selenium --collect-data googleapiclient --hidden-import selenium.webdriver.chrome.webdriver --hidden-import pystray._win32 app.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$exe = Join-Path $PSScriptRoot 'dist\HawkTimer.exe'
$icon = Join-Path $PSScriptRoot 'assets\icon.ico'
& wix build -arch x64 -d "ExePath=$exe" -d "IconPath=$icon" installer.wxs -o 'dist\HawkTimer-1.4.6-x64.msi'
if ($LASTEXITCODE -ne 0) { throw 'WiX build failed' }
