$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name HawkTimer --icon assets/icon.ico --add-data 'assets/icon.ico;.' --add-data 'mihawk_idle.gif;.' --add-data 'mihawk_action.gif;.' --add-data 'mihawk_hat.gif;.' --collect-data googleapiclient --hidden-import pystray._win32 app.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$exe = Join-Path $PSScriptRoot 'dist\HawkTimer.exe'
$signThumbprint = $env:HAWKTIMER_SIGNING_THUMBPRINT
function Sign-ReleaseFile([string]$Path) {
  if (-not $signThumbprint) { return }
  $signTool = if ($env:HAWKTIMER_SIGNTOOL) { $env:HAWKTIMER_SIGNTOOL } else { (Get-Command signtool.exe -ErrorAction Stop).Source }
  & $signTool sign /sha1 $signThumbprint /fd SHA256 /tr 'http://timestamp.digicert.com' /td SHA256 $Path
  if ($LASTEXITCODE -ne 0) { throw "Signing failed: $Path" }
  & $signTool verify /pa /v $Path
  if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $Path" }
}
Sign-ReleaseFile $exe
$icon = Join-Path $PSScriptRoot 'assets\icon.ico'
& wix build -arch x64 -d "ExePath=$exe" -d "IconPath=$icon" installer.wxs -o 'dist\HawkTimer-1.4.9-x64.msi'
if ($LASTEXITCODE -ne 0) { throw 'WiX build failed' }

Sign-ReleaseFile (Join-Path $PSScriptRoot 'dist\HawkTimer-1.4.9-x64.msi')
if (-not $signThumbprint) { Write-Warning 'No signing certificate configured; the release files are unsigned.' }
