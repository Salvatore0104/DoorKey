$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root ".hr6107_service.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "No HR-6107 service PID is recorded."
    exit 0
}
$ServicePid = [int](Get-Content $PidFile)
$Process = Get-Process -Id $ServicePid -ErrorAction SilentlyContinue
if ($Process) {
    Stop-Process -Id $ServicePid
    $Process.WaitForExit(5000)
}
Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
Write-Host "HR-6107 service stopped."
