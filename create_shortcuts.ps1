$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$root = 'c:\Users\Administrator\Documents\绿城海尔门禁系统'

$startLnk = Join-Path $desktop '启动HR-6107门禁.lnk'
$sc = $ws.CreateShortcut($startLnk)
$sc.TargetPath = Join-Path $root 'start_hr6107.bat'
$sc.WorkingDirectory = $root
$sc.IconLocation = 'shell32.dll,14'
$sc.Description = '启动 HR-6107 门禁软件终端'
$sc.Save()

$stopLnk = Join-Path $desktop '停止HR-6107门禁.lnk'
$sc2 = $ws.CreateShortcut($stopLnk)
$sc2.TargetPath = Join-Path $root 'stop_hr6107.bat'
$sc2.WorkingDirectory = $root
$sc2.IconLocation = 'shell32.dll,28'
$sc2.Description = '停止 HR-6107 门禁软件终端'
$sc2.Save()

Write-Host "桌面快捷方式已创建:"
Write-Host "  $startLnk"
Write-Host "  $stopLnk"
