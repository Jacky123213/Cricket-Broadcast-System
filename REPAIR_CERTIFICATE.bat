@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" scripts\generate_certificate.py --reuse-ca
if errorlevel 1 goto failed
powershell -NoProfile -ExecutionPolicy Bypass -Command "Import-Certificate -FilePath '%CD%\certs\rootCA.crt' -CertStoreLocation 'Cert:\CurrentUser\Root' | Out-Null"
echo Server certificate repaired. Your existing trusted CA and private keys were preserved.
pause
exit /b 0
:missing
echo Run SETUP_WINDOWS.bat first.
pause
exit /b 1
:failed
echo Certificate repair failed.
pause
exit /b 1
