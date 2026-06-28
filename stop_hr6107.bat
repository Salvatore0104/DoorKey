@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PIDFILE=%ROOT%\.hr6107_service.pid"

if not exist "%PIDFILE%" (
    echo [提示] 没有找到运行中的 HR-6107 服务记录
    echo 尝试查找残留 python 进程...
    
    REM 查找运行 run_hr6107.py 的进程并终止
    for /f "tokens=2" %%P in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2^>nul') do (
        wmic process where "ProcessId=%%P" get CommandLine 2>nul | findstr /I "run_hr6107" >nul 2>&1
        if !errorlevel! equ 0 (
            echo 正在终止残留进程 PID: %%P
            taskkill /F /PID %%P >nul 2>&1
        )
    )
    echo 完成
    timeout /t 2 >nul
    exit /b 0
)

set /p SVC_PID=<"%PIDFILE%"

echo ========================================
echo   HR-6107 门禁软件终端 - 停止
echo ========================================
echo 正在停止服务，PID: %SVC_PID%

tasklist /FI "PID eq %SVC_PID%" 2>nul | find "%SVC_PID%" >nul 2>&1
if %errorlevel% equ 0 (
    taskkill /F /PID %SVC_PID% >nul 2>&1
    if %errorlevel% equ 0 (
        echo 服务已停止
    ) else (
        echo [警告] 无法终止进程，可能需要管理员权限
    )
) else (
    echo [提示] 进程 %SVC_PID% 已不存在
)

del "%PIDFILE%" 2>nul
echo.
echo HR-6107 服务已停止
echo.
timeout /t 2 >nul
endlocal
