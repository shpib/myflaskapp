@echo off
echo ============================================
echo   Guardian Server - Setup ^& Run
echo ============================================
echo.

:: التحقق من وجود Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python غير مثبت! حمّله من: https://python.org
    pause
    exit
)

echo [1/3] Installing Flask...
pip install flask -q

echo [2/3] Creating data folders...
mkdir data 2>nul
mkdir data\photos 2>nul
mkdir static 2>nul
mkdir static\photos 2>nul

echo [3/3] Starting Guardian Server...
echo.
echo  Dashboard: http://127.0.0.1:5000
echo  Network:   http://192.168.8.199:5000
echo.
echo ============================================
python server.py
pause
