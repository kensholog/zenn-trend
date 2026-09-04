# Run a long fetch script detached from the terminal / tool timeouts.
# Usage (from repo root, PowerShell 7 recommended):
#   pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_detached.ps1 -Script scripts/jquants_fetch_daily.py -ScriptArgs "--rpm 4" -Log data/jquants/fetch.log
# Progress goes to -Log. Stop with scripts/stop_detached.ps1.
param(
    [Parameter(Mandatory = $true)][string]$Script,
    [string]$ScriptArgs = "",
    [Parameter(Mandatory = $true)][string]$Log
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$logPath = Join-Path $root $Log
$errPath = [System.IO.Path]::ChangeExtension($logPath, ".err")
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logPath) | Out-Null

# Do not start twice (exclude this process itself)
$scriptName = [System.IO.Path]::GetFileName($Script)
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.Name -like "python*" -and $_.CommandLine -like "*$scriptName*"
}
if ($running) {
    Write-Output ("already running: pid " + ($running.ProcessId -join ","))
    exit 0
}

$argList = @($Script) + ($ScriptArgs -split " " | Where-Object { $_ -ne "" })
$p = Start-Process -FilePath "python" -ArgumentList $argList -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput $logPath -RedirectStandardError $errPath -PassThru
Write-Output ("started pid " + $p.Id + " -> " + $Log)
