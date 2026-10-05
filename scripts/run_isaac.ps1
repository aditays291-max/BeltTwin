param(
    [string]$Script = 'phase1_scene.py',
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ScriptArgs
)
$ErrorActionPreference = 'Stop'
$beltRoot = Split-Path $PSScriptRoot -Parent
$isaacRoot = 'C:\Isaac Sim'
# Configure only this child process environment; never invoke the copying launcher.
$env:CARB_APP_PATH = Join-Path $isaacRoot 'kit'
$env:ISAAC_PATH = $isaacRoot
$env:EXP_PATH = Join-Path $isaacRoot 'apps'
$env:PYTHONPATH = Join-Path $isaacRoot 'site'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUNBUFFERED = '1'
Set-Location $beltRoot
& "$isaacRoot\kit\python\python.exe" -B "$PSScriptRoot\$Script" @ScriptArgs
exit $LASTEXITCODE

