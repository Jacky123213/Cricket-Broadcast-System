param(
    [string]$Python = '',
    [string]$Compiler = '',
    [switch]$SkipTests
)
$ErrorActionPreference = 'Stop'
$buildRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $buildRoot '.build-venv\Scripts\python.exe' }
if (-not $Compiler) { $Compiler = Join-Path $buildRoot '.tools\InnoSetup\ISCC.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Build Python not found. See INSTALLER_README.md.' }
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Inno compiler not found. See INSTALLER_README.md.' }
$runtimeBootstrapper = Join-Path $buildRoot '.tools\MicrosoftEdgeWebview2Setup.exe'
if (-not (Test-Path -LiteralPath $runtimeBootstrapper)) { throw 'Download the official WebView2 bootstrapper before building.' }
$runtimeSignature = Get-AuthenticodeSignature -LiteralPath $runtimeBootstrapper
if ($runtimeSignature.Status -ne 'Valid' -or $runtimeSignature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
    throw 'WebView2 prerequisite does not have a valid Microsoft signature; refusing to bundle it.'
}
Push-Location $buildRoot
try {
    if (-not $SkipTests) {
        $testParent = Join-Path $buildRoot '.installer-test'
        New-Item -ItemType Directory -Path $testParent -Force | Out-Null
        $testFolder = Join-Path $testParent ('pytest-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
        & $Python -m pytest tests -q --basetemp $testFolder
        if ($LASTEXITCODE -ne 0) { throw 'Automated tests failed; installer was not built.' }
    }
    & $Python scripts/build_metadata.py notices
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate third-party notices' }
    & $Python -m PyInstaller --noconfirm --clean --log-level WARN packaging/CricketBroadcastSystem.spec
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
    & $Python scripts/build_metadata.py audit
    if ($LASTEXITCODE -ne 0) { throw 'Bundle privacy audit failed' }
    & $Compiler /Q packaging/CricketBroadcastSystem.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
    Get-FileHash -LiteralPath (Join-Path $buildRoot 'dist\CricketBroadcastSystem-Setup.exe') -Algorithm SHA256
} finally { Pop-Location }
