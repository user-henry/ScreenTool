@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   ScreenTool - 构建发布包
echo ============================================
echo.

:: 1. 终止旧进程
echo [1/4] 终止旧进程...
taskkill /F /IM ScreenTool.exe >nul 2>&1

:: 2. PyInstaller 构建
echo [2/4] PyInstaller 构建 EXE...
pyinstaller --clean --noconfirm ScreenTool.spec
if errorlevel 1 (
    echo [错误] 构建失败！
    pause
    exit /b 1
)

:: 3. 复制发布文件
echo [3/4] 准备发布目录...
rmdir /s /q release 2>nul
mkdir release
copy /Y dist\ScreenTool.exe release\ScreenTool.exe
xcopy /E /I /Y models release\models

:: 4. 打包 ZIP
echo [4/4] 创建 ZIP 压缩包...
set "ZIPFILE=ScreenTool_v2.3.0_portable.zip"
if exist "%ZIPFILE%" del /f /q "%ZIPFILE%"
powershell -NoProfile -Command "Compress-Archive -Path 'release\*' -DestinationPath '%ZIPFILE%' -Force"

echo.
echo ============================================
echo   构建完成！
echo   - EXE: release\ScreenTool.exe
echo   - ZIP: %ZIPFILE%
echo ============================================
echo.
echo   分发方式：
echo   1. 直接发送 %ZIPFILE% 给他人
echo   2. 对方解压后运行 ScreenTool.exe 即可
echo   3. 无需安装，解压即用（便携版）
echo.
pause
