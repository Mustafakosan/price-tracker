@echo off
REM One-click setup and self-test for Windows.
REM Creates .venv, installs requirements, runs tests, the offline demo and a real check.
REM Results are written to test_log.txt next to this file.

chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "LOG=%~dp0test_log.txt"

echo ===== %date% %time% ===== > "%LOG%"

set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"

echo ===== PYTHON ===== >> "%LOG%"
%PY% --version >> "%LOG%" 2>&1
if errorlevel 1 (
    echo PYTHON NOT FOUND >> "%LOG%"
    goto end
)

echo ===== SETUP ===== >> "%LOG%"
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv >> "%LOG%" 2>&1
set "VPY=.venv\Scripts\python.exe"
"%VPY%" -m pip install --disable-pip-version-check -q -r requirements-dev.txt >> "%LOG%" 2>&1

echo ===== TESTS ===== >> "%LOG%"
"%VPY%" -m pytest -q >> "%LOG%" 2>&1

echo ===== DEMO ===== >> "%LOG%"
"%VPY%" examples\demo.py >> "%LOG%" 2>&1

echo ===== REAL SITE ===== >> "%LOG%"
"%VPY%" -m tracker -c config.example.toml --no-notify >> "%LOG%" 2>&1

:end
echo ===== DONE ===== >> "%LOG%"
echo.
echo Bitti / Done. Sonuclar: test_log.txt
timeout /t 5 >nul
