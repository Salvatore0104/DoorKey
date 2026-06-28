@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PYTHON=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "PIDFILE=%ROOT%\.hr6107_service.pid"

REM 检查是否已在运行
if exist "%PIDFILE%" (
    for /f %%P in (%PIDFILE%) do (
        tasklist /FI "PID eq %%P" 2>nul | find "%%P" >nul 2>&1
        if !errorlevel! equ 0 (
            echo [错误] HR-6107 服务已在运行，PID: %%P
            echo 请先运行 stop_hr6107.bat 停止服务
            pause
            exit /b 1
        )
    )
    del "%PIDFILE%" 2>nul
)

REM 设置环境变量
set "HR6107_DEVICE_IP=172.30.2.47"
set "HR6107_WEB_HOST=127.0.0.1"
set "HR6107_WEB_PORT=8088"

echo ========================================
echo   HR-6107 门禁软件终端 - 启动
echo ========================================
echo 项目目录: %ROOT%
echo Python:   %PYTHON%
echo 访问地址: http://%HR6107_WEB_HOST%:%HR6107_WEB_PORT%/
echo ----------------------------------------

REM 后台启动服务
set "LOGFILE=%ROOT%\hr6107_console.log"
set "ERRFILE=%ROOT%\hr6107_console.error.log"

start "" /B "%PYTHON%" "%ROOT%\run_hr6107.py" > "%LOGFILE%" 2> "%ERRFILE%"

REM 获取刚启动的 python 进程 PID
timeout /t 2 /nobreak >nul
for /f "tokens=2" %%I in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST 2^>nul ^| findstr /I "PID"') do (
    set "SVC_PID=%%I"
)

if not defined SVC_PID (
    echo [错误] 服务启动失败，请查看日志:
    echo   %ERRFILE%
    pause
    exit /b 1
)

echo %SVC_PID%> "%PIDFILE%"
echo 服务已启动，PID: %SVC_PID%
echo 日志文件: %LOGFILE%
echo.
echo 访问地址: http://%HR6107_WEB_HOST%:%HR6107_WEB_PORT%/

if exist "%ROOT%\.hr6107_api_token" (
    set /p TOKEN=<"%ROOT%\.hr6107_api_token"
    echo 访问令牌: !TOKEN!
) else (
    echo 认证: 已禁用（本地访问）
)

echo.
echo 提示: 此窗口可关闭，服务在后台运行
echo 停止服务请运行 stop_hr6107.bat
echo.
timeout /t 3 >nul
endlocal
