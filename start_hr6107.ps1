param(
    [string]$DeviceIp = "172.30.2.47",
    [string]$WebHost = "127.0.0.1",
    [int]$WebPort = 8088
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$PidFile = Join-Path $Root ".hr6107_service.pid"
$LogFile = Join-Path $Root "hr6107_console.log"
$ErrorLogFile = Join-Path $Root "hr6107_console.error.log"

if (Test-Path $PidFile) {
    $OldPid = [int](Get-Content $PidFile)
    if (Get-Process -Id $OldPid -ErrorAction SilentlyContinue) {
        throw "HR-6107 service is already running (PID $OldPid)."
    }
    Remove-Item -LiteralPath $PidFile
}

$Assigned = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -eq $DeviceIp }
if (-not $Assigned -and $DeviceIp -ne "127.0.0.1") {
    throw "The device IP $DeviceIp is not assigned to this computer."
}

$env:HR6107_DEVICE_IP = $DeviceIp
$env:HR6107_WEB_HOST = $WebHost
$env:HR6107_WEB_PORT = "$WebPort"
$Process = Start-Process -FilePath $Python -ArgumentList "run_hr6107.py" -WorkingDirectory $Root `
    -RedirectStandardOutput $LogFile -RedirectStandardError $ErrorLogFile -WindowStyle Hidden -PassThru
Set-Content -LiteralPath $PidFile -Value $Process.Id -Encoding ascii
Start-Sleep -Seconds 2
if (-not (Get-Process -Id $Process.Id -ErrorAction SilentlyContinue)) {
    Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
    throw "Service failed to start. See $LogFile and $ErrorLogFile."
}

Write-Host "HR-6107 service: http://$WebHost`:$WebPort/"
$TokenPath = Join-Path $Root ".hr6107_api_token"
if (Test-Path $TokenPath) {
    $Token = Get-Content $TokenPath
    Write-Host "Access token: $Token"
} else {
    Write-Host "Authentication: disabled (local access)"
}
Write-Host "PID: $($Process.Id)"
