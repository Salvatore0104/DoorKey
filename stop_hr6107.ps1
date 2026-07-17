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
    $CommandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $ServicePid" -ErrorAction SilentlyContinue).CommandLine
    if ($Process.ProcessName -like "python*" -and $CommandLine -match "run_hr6107\.py") {
        Stop-Process -Id $ServicePid
        $Process.WaitForExit(5000)
    } else {
        Write-Warning "PID $ServicePid no longer belongs to HR-6107; removing stale PID file only."
    }
}
Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
Write-Host "HR-6107 service stopped."
