@echo off
chcp 65001 >nul
title 快手直播录制+分析工具

echo.
echo ========================================
echo   🎥 快手直播录制+分析工具
echo ========================================
echo.

if "%~1"=="" (
    echo 用法: 拖拽快手直播链接到此文件
    echo 或者: run.bat https://live.kuaishou.com/u/xxx
    echo.
    set /p URL="请输入快手直播链接: "
) else (
    set URL=%~1
)

echo.
echo 正在启动...
echo 链接: %URL%
echo.

python main.py "%URL%" -d 120

echo.
echo 分析完成！查看 output/reports/ 文件夹
pause
