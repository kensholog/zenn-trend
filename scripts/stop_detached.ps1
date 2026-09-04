# Stop a python script started by run_detached.ps1.
# Usage: pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/stop_detached.ps1 -Script jquants_fetch_daily.py
param([Parameter(Mandatory = $true)][string]$Script)
$name = [System.IO.Path]::GetFileName($Script)
$ps = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.Name -like "python*" -and $_.CommandLine -like "*$name*"
}
if (-not $ps) { Write-Output "not running"; exit 0 }
foreach ($p in $ps) { Stop-Process -Id $p.ProcessId -Force; Write-Output ("stopped pid " + $p.ProcessId) }
