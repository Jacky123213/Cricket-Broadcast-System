@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install 64-bit Python 3.11 or newer.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating the Backyard Cricket Studio environment...
  py -3.11 -m venv .venv
  if errorlevel 1 py -3 -m venv .venv
)
echo Installing application packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
if exist "certs\server.crt" if exist "certs\server.key.pem" goto ready
echo Creating a private local HTTPS certificate...
".venv\Scripts\python.exe" scripts\generate_certificate.py
if errorlevel 1 goto failed
powershell -NoProfile -ExecutionPolicy Bypass -Command "Import-Certificate -FilePath '%CD%\certs\rootCA.crt' -CertStoreLocation 'Cert:\CurrentUser\Root' | Out-Null"
:ready
echo.
echo Setup complete. Double-click START_STUDIO.bat.
pause
exit /b 0
:failed
echo.
echo Setup failed. Read the error above, then open TROUBLESHOOTING.md.
pause
exit /b 1
